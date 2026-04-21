import asyncio
import logging
import time

import httpx

from providers.base import BaseProvider

logger = logging.getLogger(__name__)

GLADIA_BASE = "https://api.gladia.io/v2"


class GladiaProvider(BaseProvider):
    name = "gladia"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def transcribe(self, audio_path: str, language: str) -> dict:
        return await asyncio.to_thread(self._transcribe_sync, audio_path, language)

    def _transcribe_sync(self, audio_path: str, language: str) -> dict:
        headers = {"x-gladia-key": self.api_key}

        with httpx.Client(timeout=300) as client:
            with open(audio_path, "rb") as f:
                upload_resp = client.post(
                    f"{GLADIA_BASE}/upload",
                    headers=headers,
                    files={"audio": (audio_path.split("/")[-1].split("\\")[-1], f, "audio/mpeg")},
                )
            upload_resp.raise_for_status()
            audio_url = upload_resp.json()["audio_url"]

            transcription_resp = client.post(
                f"{GLADIA_BASE}/transcription",
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "audio_url": audio_url,
                    "language": language,
                },
            )
            transcription_resp.raise_for_status()
            result_url = transcription_resp.json()["result_url"]

            for _ in range(120):
                poll_resp = client.get(result_url, headers=headers)
                poll_resp.raise_for_status()
                data = poll_resp.json()

                if data["status"] == "done":
                    full_transcript = data["result"]["transcription"]["full_transcript"]
                    return {"transcript": full_transcript}

                if data["status"] == "error":
                    raise RuntimeError(f"Gladia error: {data.get('error', 'unknown')}")

                time.sleep(2)

            raise TimeoutError("Gladia transcription timed out after 4 minutes")
