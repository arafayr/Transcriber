import time
import logging

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse

from yt_dlp.utils import DownloadError

from config import get_settings
from models import TranscribeRequest, TranscribeResponse, ErrorResponse, HealthResponse, ProviderName
from audio_extractor import AudioExtractor
from provider_router import ProviderRouter, AllProvidersFailedError, RateLimitError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(title="Transcriber API", version="1.0.0")
extractor = AudioExtractor()
router = ProviderRouter()


@app.post("/transcribe", response_model=TranscribeResponse, responses={500: {"model": ErrorResponse}})
async def transcribe(req: TranscribeRequest):
    start = time.time()
    extracted = None
    try:
        provider_name = req.provider.value
        if provider_name == "auto" and not router.available_providers():
            raise AllProvidersFailedError("No providers configured — add at least one API key to .env")
        if provider_name != "auto" and provider_name not in router.available_providers():
            raise ValueError(f"Provider '{provider_name}' is not configured (API key missing)")

        extracted = await extractor.extract(req.video_url)
        result = await router.transcribe(
            audio_path=extracted.file_path,
            language=req.language,
            provider_name=provider_name,
        )
        elapsed_ms = round((time.time() - start) * 1000, 1)
        return TranscribeResponse(
            transcript=result["transcript"],
            provider_used=result["provider_used"],
            duration_seconds=extracted.duration_seconds,
            processing_time_ms=elapsed_ms,
        )
    except RateLimitError as e:
        return JSONResponse(
            status_code=429,
            content=ErrorResponse(
                error="RATE_LIMITED",
                message=f"Provider '{e.provider}' is rate limited. Try again later or use provider=auto for fallback.",
            ).model_dump(),
        )
    except AllProvidersFailedError as e:
        return JSONResponse(
            status_code=502,
            content=ErrorResponse(
                error="ALL_PROVIDERS_FAILED",
                message=str(e),
            ).model_dump(),
        )
    except (ValueError, DownloadError) as e:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(error="BAD_REQUEST", message=str(e)).model_dump(),
        )
    except Exception as e:
        logging.getLogger(__name__).exception("Unhandled error")
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(error="INTERNAL_ERROR", message=str(e)).model_dump(),
        )
    finally:
        if extracted:
            AudioExtractor.cleanup(extracted.file_path)


ALLOWED_EXTENSIONS = {
    "mp3", "mp4", "m4a", "wav", "webm", "ogg", "flac", "aac",
    "mkv", "avi", "mov", "wmv", "mpga", "mpeg",
}


@app.post("/transcribe/upload", response_model=TranscribeResponse, responses={500: {"model": ErrorResponse}})
async def transcribe_upload(
    file: UploadFile = File(..., description="Audio or video file to transcribe"),
    provider: str = Form(default="auto", description="auto | groq | gemini | assemblyai | deepgram | gladia"),
    language: str = Form(default="en", description="BCP-47 language code"),
):
    start = time.time()
    extracted = None
    try:
        provider_name = ProviderName(provider).value
        if provider_name == "auto" and not router.available_providers():
            raise AllProvidersFailedError("No providers configured — add at least one API key to .env")
        if provider_name != "auto" and provider_name not in router.available_providers():
            raise ValueError(f"Provider '{provider_name}' is not configured (API key missing)")

        ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type '.{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )

        settings = get_settings()
        max_bytes = settings.max_upload_size_mb * 1024 * 1024
        file_data = await file.read()
        if len(file_data) > max_bytes:
            raise ValueError(f"File too large ({len(file_data) / 1024 / 1024:.0f} MB). Maximum is {settings.max_upload_size_mb} MB.")

        extracted = await extractor.save_upload(file_data, file.filename or "upload.mp3")
        result = await router.transcribe(
            audio_path=extracted.file_path,
            language=language,
            provider_name=provider_name,
        )
        elapsed_ms = round((time.time() - start) * 1000, 1)
        return TranscribeResponse(
            transcript=result["transcript"],
            provider_used=result["provider_used"],
            duration_seconds=extracted.duration_seconds,
            processing_time_ms=elapsed_ms,
        )
    except RateLimitError as e:
        return JSONResponse(
            status_code=429,
            content=ErrorResponse(
                error="RATE_LIMITED",
                message=f"Provider '{e.provider}' is rate limited. Try again later or use provider=auto for fallback.",
            ).model_dump(),
        )
    except AllProvidersFailedError as e:
        return JSONResponse(
            status_code=502,
            content=ErrorResponse(error="ALL_PROVIDERS_FAILED", message=str(e)).model_dump(),
        )
    except (ValueError, DownloadError) as e:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(error="BAD_REQUEST", message=str(e)).model_dump(),
        )
    except Exception as e:
        logging.getLogger(__name__).exception("Unhandled error")
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(error="INTERNAL_ERROR", message=str(e)).model_dump(),
        )
    finally:
        if extracted:
            AudioExtractor.cleanup(extracted.file_path)


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(providers_available=router.available_providers())
