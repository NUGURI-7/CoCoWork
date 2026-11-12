"""将已确认的播报稿合成为人声 WAV，再用选定的配乐制作 MP3。"""

import asyncio
import logging
import math
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

import httpx

from app.agents.library.store_marketing_audio.presets import (
    DEFAULT_MUSIC_KEY,
    DEFAULT_VOICE_KEY,
    MUSIC_PRESETS,
    VOICE_PRESETS,
)
from app.core.config import settings


logger = logging.getLogger(__name__)

_TTS_ENDPOINT = "https://maas.qianwenaiapi.com/api/v1/services/audio/tts/SpeechSynthesizer"
_TTS_MODEL = "qwen-audio-3.0-tts-flash"
_SAMPLE_RATE = 24_000
_MAX_WAV_BYTES = 10 * 1024 * 1024
_HTTP_TIMEOUT = 45
_MEDIA_TIMEOUT = 60
_AUDIO_HOST_SUFFIXES = (".aliyuncs.com", ".qianwenaiapi.com", ".aliyun.com")


class AudioProductionError(RuntimeError):
    """音频制作失败，可向调用方报告阶段相关的错误。"""


async def synthesize_voice(text: str, voice_key: str = DEFAULT_VOICE_KEY) -> bytes:
    """按音色预设合成 24 kHz 人声 WAV，返回可供后续重复混音的文件字节。"""
    text = text.strip()
    if not text:
        raise ValueError("播报文案不能为空")
    preset = VOICE_PRESETS.get(voice_key)
    if preset is None:
        raise ValueError("未知的音色选项")

    api_key = settings.DASHSCOPE_API_KEY.get_secret_value().strip()
    if not api_key:
        raise AudioProductionError("尚未配置千问语音合成凭证")

    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.post(
                _TTS_ENDPOINT,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": _TTS_MODEL,
                    "input": {
                        "text": text,
                        "voice": preset.voice,
                        "instruction": preset.instruction,
                        "rate": preset.rate,
                        "format": "wav",
                        "sample_rate": _SAMPLE_RATE,
                    },
                },
            )
            if not response.is_success:
                raise AudioProductionError(f"千问语音合成失败（HTTP {response.status_code}）")
            try:
                audio_url = response.json()["output"]["audio"]["url"]
            except (KeyError, TypeError, ValueError):
                raise AudioProductionError("千问语音合成未返回人声音频") from None
            wav_bytes = await _download_wav(client, audio_url)
    except httpx.RequestError as exc:
        raise AudioProductionError(f"千问语音合成或音频下载失败（{type(exc).__name__}）") from None

    # 服务返回的 WAV 可能带流式长度占位，重新写文件头后再交给后续调用方。
    with TemporaryDirectory(prefix="cocowork-voice-") as directory:
        output = Path(directory) / "voice.wav"
        await _run_media(
            "ffmpeg", "-nostdin", "-v", "error", "-f", "wav", "-i", "pipe:0",
            "-c:a", "pcm_s16le", str(output), input_bytes=wav_bytes,
        )
        return await asyncio.to_thread(output.read_bytes)


async def _download_wav(client: httpx.AsyncClient, audio_url: object) -> bytes:
    if not isinstance(audio_url, str):
        raise AudioProductionError("千问返回了无效的音频地址")
    try:
        url = urlsplit(audio_url)
        port = url.port
    except ValueError:
        raise AudioProductionError("千问返回了无效的音频地址") from None
    if (
        url.scheme not in {"http", "https"}
        or not (url.hostname or "").endswith(_AUDIO_HOST_SUFFIXES)
        or url.username is not None
        or port not in {None, 443}
    ):
        raise AudioProductionError("千问返回了无效的音频地址")

    # 百炼可能返回 http 链接。下载走 HTTPS，且不向存储域发送 API Key。
    wav = bytearray()
    async with client.stream("GET", url._replace(scheme="https").geturl()) as response:
        if not response.is_success:
            raise AudioProductionError(f"人声音频下载失败（HTTP {response.status_code}）")
        async for chunk in response.aiter_bytes():
            if len(wav) + len(chunk) > _MAX_WAV_BYTES:
                raise AudioProductionError("人声音频超过制作大小限制")
            wav.extend(chunk)
    if wav[:4] != b"RIFF" or wav[8:12] != b"WAVE":
        raise AudioProductionError("下载的人声文件不是有效的 WAV")
    return bytes(wav)


async def mix_audio(voice_wav: bytes, music_key: str = DEFAULT_MUSIC_KEY) -> bytes:
    """复用已有的 WAV，压低配乐并淡出，成品时长以人声为准。"""
    preset = MUSIC_PRESETS.get(music_key)
    if preset is None:
        raise ValueError("未知的配乐选项")
    if not preset.path.is_file():
        raise AudioProductionError("配乐文件不存在")

    with TemporaryDirectory(prefix="cocowork-mix-") as directory:
        voice_file = Path(directory) / "voice.wav"
        output = Path(directory) / "broadcast.mp3"
        await asyncio.to_thread(voice_file.write_bytes, voice_wav)
        probe = await _run_media(
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "csv=p=0", str(voice_file),
        )
        try:
            duration = float(probe.strip())
        except ValueError:
            raise AudioProductionError("无法读取人声音频时长") from None
        if not math.isfinite(duration) or duration <= 0:
            raise AudioProductionError("人声音频时长无效")

        fade = min(0.8, duration)
        filters = (
            "[0:a]volume=0.90[voice];"
            f"[1:a]volume=0.12,afade=t=out:st={duration - fade:.3f}:d={fade:.3f}[music];"
            "[voice][music]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[out]"
        )
        await _run_media(
            "ffmpeg", "-nostdin", "-v", "error", "-i", str(voice_file),
            "-stream_loop", "-1", "-i", str(preset.path),
            "-filter_complex", filters, "-map", "[out]", "-c:a", "libmp3lame",
            "-b:a", "128k", str(output),
        )
        return await asyncio.to_thread(output.read_bytes)


async def _run_media(program: str, *args: str, input_bytes: bytes | None = None) -> bytes:
    try:
        process = await asyncio.create_subprocess_exec(
            program, *args,
            stdin=asyncio.subprocess.PIPE if input_bytes is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError:
        raise AudioProductionError(f"无法启动 {program}，请检查音频处理环境") from None

    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(input_bytes), _MEDIA_TIMEOUT)
    except (TimeoutError, asyncio.CancelledError) as exc:
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        await process.communicate()
        if isinstance(exc, TimeoutError):
            raise AudioProductionError(f"{program} 音频处理超时") from None
        raise
    if process.returncode:
        logger.warning("%s 音频处理失败：%s", program, stderr.decode(errors="replace")[-1500:].strip())
        raise AudioProductionError(f"{program} 音频处理失败")
    return stdout
