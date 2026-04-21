from abc import ABC, abstractmethod


class BaseProvider(ABC):
    name: str

    @abstractmethod
    async def transcribe(self, audio_path: str, language: str) -> dict:
        """
        Returns: {"transcript": str}
        """
        ...
