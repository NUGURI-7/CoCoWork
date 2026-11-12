"""门店营销音频制作的音色和配乐选项。"""

from dataclasses import dataclass
from pathlib import Path


_PROMOTION_INSTRUCTION = (
    "像在店门口招呼路过顾客一样，用清楚的普通话，明快有劲，句尾有明显起落。"
    "把开头的招呼喊亮一些，连接句利落地带过。"
    "读到优惠和价格时先停半拍，重读数量和价格，读清每个字。"
    "最后一句略抬音，结束干脆。"
)


@dataclass(frozen=True)
class VoicePreset:
    label: str
    voice: str
    rate: float = 1.18
    instruction: str = _PROMOTION_INSTRUCTION


@dataclass(frozen=True)
class MusicPreset:
    label: str
    path: Path


DEFAULT_VOICE_KEY = "market_male"
VOICE_PRESETS = {
    DEFAULT_VOICE_KEY: VoicePreset("热情男声", "longchuanshu_v3.6"),
    "bright_female": VoicePreset("活泼女声", "longanxiaoxin"),
}

DEFAULT_MUSIC_KEY = "banana_track"
MUSIC_PRESETS = {
    DEFAULT_MUSIC_KEY: MusicPreset(
        "轻快配乐",
        Path(__file__).resolve().parents[3] / "assets" / "audio" / "banana_track.ogg",
    ),
}
