from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class ProviderName(str, Enum):
    AUTO = "auto"
    GROQ = "groq"
    GEMINI = "gemini"
    ASSEMBLYAI = "assemblyai"
    DEEPGRAM = "deepgram"
    GLADIA = "gladia"


class TranscribeRequest(BaseModel):
    video_url: str = Field(..., description="URL of the video or audio to transcribe")
    provider: ProviderName = ProviderName.AUTO
    language: str = Field(default="en", description="BCP-47 language code")


class TranscribeResponse(BaseModel):
    transcript: str
    provider_used: str
    duration_seconds: Optional[float] = None
    processing_time_ms: float


class ErrorResponse(BaseModel):
    error: str
    message: str


class HealthResponse(BaseModel):
    status: str = "ok"
    providers_available: list[str]
