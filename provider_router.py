import time
import logging

from config import get_settings
from providers.base import BaseProvider
from providers.groq_provider import GroqProvider
from providers.gemini_provider import GeminiProvider
from providers.assemblyai_provider import AssemblyAIProvider
from providers.deepgram_provider import DeepgramProvider
from providers.gladia_provider import GladiaProvider

logger = logging.getLogger(__name__)

PROVIDER_ORDER = ["groq", "gemini", "assemblyai", "deepgram", "gladia"]
COOLDOWN_SECONDS = 300


class ProviderRouter:
    def __init__(self):
        self.settings = get_settings()
        self._cooldowns: dict[str, float] = {}
        self._providers: dict[str, BaseProvider] = {}
        self._init_providers()

    def _init_providers(self):
        key_map = {
            "groq": self.settings.groq_api_key,
            "gemini": self.settings.gemini_api_key,
            "assemblyai": self.settings.assemblyai_api_key,
            "deepgram": self.settings.deepgram_api_key,
            "gladia": self.settings.gladia_api_key,
        }
        factory = {
            "groq": GroqProvider,
            "gemini": GeminiProvider,
            "assemblyai": AssemblyAIProvider,
            "deepgram": DeepgramProvider,
            "gladia": GladiaProvider,
        }
        for name, key in key_map.items():
            if key:
                self._providers[name] = factory[name](key)

    def available_providers(self) -> list[str]:
        return [name for name in PROVIDER_ORDER if name in self._providers]

    def _is_cooling_down(self, name: str) -> bool:
        deadline = self._cooldowns.get(name, 0)
        if time.time() < deadline:
            return True
        if deadline:
            del self._cooldowns[name]
        return False

    def _mark_rate_limited(self, name: str):
        self._cooldowns[name] = time.time() + COOLDOWN_SECONDS
        logger.warning("Provider %s rate-limited, cooling down for %ds", name, COOLDOWN_SECONDS)

    async def transcribe(self, audio_path: str, language: str, provider_name: str = "auto") -> dict:
        if provider_name != "auto":
            return await self._try_provider(provider_name, audio_path, language)

        errors = []
        for name in PROVIDER_ORDER:
            if name not in self._providers:
                continue
            if self._is_cooling_down(name):
                logger.info("Skipping %s (cooling down)", name)
                continue
            try:
                result = await self._try_provider(name, audio_path, language)
                return result
            except RateLimitError:
                self._mark_rate_limited(name)
                errors.append(f"{name}: rate limited")
            except Exception as e:
                logger.error("Provider %s failed: %s", name, e)
                errors.append(f"{name}: {e}")

        raise AllProvidersFailedError(
            f"All available providers failed or are rate limited. Details: {'; '.join(errors)}"
        )

    async def _try_provider(self, name: str, audio_path: str, language: str) -> dict:
        if name not in self._providers:
            raise ValueError(f"Provider '{name}' is not configured (API key missing)")

        provider = self._providers[name]
        try:
            result = await provider.transcribe(audio_path, language)
            result["provider_used"] = name
            return result
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "rate" in err_str and "limit" in err_str:
                raise RateLimitError(name) from e
            raise


class RateLimitError(Exception):
    def __init__(self, provider: str):
        self.provider = provider
        super().__init__(f"Rate limited by {provider}")


class AllProvidersFailedError(Exception):
    pass
