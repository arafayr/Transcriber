import asyncio
import base64
import logging
import mimetypes

from google import genai

from providers.base import BaseProvider

logger = logging.getLogger(__name__)


class GeminiProvider(BaseProvider):
    name = "gemini"

    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    async def transcribe(self, audio_path: str, language: str) -> dict:
        return await asyncio.to_thread(self._transcribe_sync, audio_path, language)

    def _transcribe_sync(self, audio_path: str, language: str) -> dict:
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        mime_type = mimetypes.guess_type(audio_path)[0] or "audio/mpeg"

        prompt = (
            f"Transcribe the following audio accurately and completely. "
            f"The audio language is '{language}'. "
            f"Return ONLY the raw transcript text — no timestamps, no speaker labels, "
            f"no formatting, no commentary."
        )

        response = self.client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                prompt,
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": audio_b64,
                    }
                },
            ],
        )

        transcript = response.text.strip()
        return {"transcript": transcript}
