"""SAQ 门店营销音频制作任务：配音 → 混音 → 存储，产物挂到发起制作的那条消息上。"""

import io
from uuid import UUID

from saq.types import Context

from app.agents.library.store_marketing_audio.audio import mix_audio, synthesize_voice
from app.core.storage import storage
from app.models import Message
from app.models.sandbox import SandboxArtifact

_FILENAME = "门店播报.mp3"
_CONTENT_TYPE = "audio/mpeg"


async def produce_marketing_audio_task(
        ctx: Context, *, message_id: str, script: str, voice_key: str, music_key: str,
) -> str:
    """制作一条播报 MP3，返回产物 ID。同一条消息已有成品时直接返回，不重复制作。"""
    message = await Message.filter(id=UUID(message_id)).select_related("conversation").get()
    existing = await SandboxArtifact.get_or_none(message_id=message.id, filename=_FILENAME)
    if existing is not None:
        return str(existing.id)

    voice = await synthesize_voice(script, voice_key)
    mp3 = await mix_audio(voice, music_key)

    conversation = message.conversation
    storage_key = f"marketing-audio/{conversation.id}/{message.id}/{_FILENAME}"
    await storage.save(storage_key, io.BytesIO(mp3), content_type=_CONTENT_TYPE)
    artifact = await SandboxArtifact.create(
        created_by_id=conversation.created_by_id,
        conversation_id=conversation.id,
        message_id=message.id,
        filename=_FILENAME,
        size=len(mp3),
        content_type=_CONTENT_TYPE,
        storage_key=storage_key,
    )
    return str(artifact.id)
