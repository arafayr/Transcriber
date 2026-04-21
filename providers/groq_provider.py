import asyncio
import os
import logging

from groq import Groq

from providers.base import BaseProvider
from audio_extractor import AudioExtractor

logger = logging.getLogger(__name__)


class GroqProvider(BaseProvider):
    name = "groq"

    def __init__(self, api_key: str):
        self.client = Groq(api_key=api_key)
        self.extractor = AudioExtractor()

    async def transcribe(self, audio_path: str, language: str) -> dict:
        return await asyncio.to_thread(self._transcribe_sync, audio_path, language)

    def _transcribe_sync(self, audio_path: str, language: str) -> dict:
        wav_path = self.extractor.resample_to_wav(audio_path)
        temp_files = [wav_path]

        try:
            chunks = self.extractor.split_audio(wav_path)
            if len(chunks) > 1:
                temp_files.extend(chunks)

            transcripts = []
            for chunk_path in chunks:
                with open(chunk_path, "rb") as f:
                    response = self.client.audio.transcriptions.create(
                        model="whisper-large-v3-turbo",
                        file=f,
                        language=language,
                        response_format="verbose_json",
                    )
                transcripts.append(response.text)

            return {"transcript": " ".join(transcripts)}
        finally:
            self.extractor.cleanup(*temp_files)
