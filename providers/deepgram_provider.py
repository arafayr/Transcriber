import asyncio
import logging

from deepgram import DeepgramClient

from providers.base import BaseProvider

logger = logging.getLogger(__name__)


class DeepgramProvider(BaseProvider):
    name = "deepgram"

    def __init__(self, api_key: str):
        self.client = DeepgramClient(api_key=api_key)

    async def transcribe(self, audio_path: str, language: str) -> dict:
        return await asyncio.to_thread(self._transcribe_sync, audio_path, language)

    def _transcribe_sync(self, audio_path: str, language: str) -> dict:
        with open(audio_path, "rb") as f:
            buffer_data = f.read()

        response = self.client.listen.v1.media.transcribe_file(
            request=buffer_data,
            model="nova-2",
            language=language,
            smart_format=True,
        )

        transcript = response.results.channels[0].alternatives[0].transcript
        return {"transcript": transcript}
