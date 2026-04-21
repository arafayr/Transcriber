import asyncio
import logging

import assemblyai as aai

from providers.base import BaseProvider

logger = logging.getLogger(__name__)


class AssemblyAIProvider(BaseProvider):
    name = "assemblyai"

    def __init__(self, api_key: str):
        aai.settings.api_key = api_key

    async def transcribe(self, audio_path: str, language: str) -> dict:
        return await asyncio.to_thread(self._transcribe_sync, audio_path, language)

    def _transcribe_sync(self, audio_path: str, language: str) -> dict:
        config = aai.TranscriptionConfig(
            speech_models=["universal-2"],
            language_code=language,
        )
        transcriber = aai.Transcriber()
        transcript = transcriber.transcribe(audio_path, config=config)

        if transcript.status == aai.TranscriptStatus.error:
            raise RuntimeError(f"AssemblyAI error: {transcript.error}")

        return {"transcript": transcript.text}
