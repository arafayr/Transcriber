from pydantic_settings import BaseSettings
from functools import lru_cache
import os

#new file


class Settings(BaseSettings):
    groq_api_key: str = ""
    gemini_api_key: str = ""
    assemblyai_api_key: str = ""
    deepgram_api_key: str = ""
    gladia_api_key: str = ""

    default_provider: str = "auto"
    max_duration_seconds: int = 3600
    max_upload_size_mb: int = 500
    temp_dir: str = os.path.join(os.path.expanduser("~"), ".transcriber_tmp")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
