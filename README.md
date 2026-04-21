# Transcriber API

A FastAPI service that transcribes video and audio into text. Give it a URL or upload a file — it extracts the audio, sends it to a transcription provider, and returns the transcript as JSON.

```
                         ┌──────────────────┐
  YouTube URL ──────────►│                  │
  Twitter URL ──────────►│   Transcriber    │──── JSON transcript
  Any video URL ────────►│      API         │
  Direct .mp3/.mp4 URL ─►│                  │
  Uploaded file ────────►│  (FastAPI)       │
                         └──────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
                  yt-dlp      FFmpeg     Provider
               (download)   (convert)  (transcribe)
```

Supports 5 free transcription providers with automatic fallback — if one fails, it tries the next.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Endpoints](#endpoints)
3. [How to Call Each Endpoint](#how-to-call-each-endpoint)
4. [Supported URL Types](#supported-url-types)
5. [Providers](#providers)
6. [Configuration](#configuration)
7. [Project Structure](#project-structure)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

### 1. Install

```bash
cd transcriber
python -m venv venv
```

Activate the virtual environment:

```bash
# Windows
venv\Scripts\activate

# Linux / Mac
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### 2. Add API keys

```bash
cp .env.example .env
```

Open `.env` in any text editor and paste in your API keys. You only need **one** provider to get started. Groq is the fastest and easiest:

| Provider | Where to get the key | Time to sign up |
|---|---|---|
| Groq | https://console.groq.com/keys | 30 seconds |
| Gemini | https://aistudio.google.com/apikey | 1 minute |
| AssemblyAI | https://www.assemblyai.com/dashboard/signup | 1 minute |
| Deepgram | https://console.deepgram.com/signup | 1 minute |
| Gladia | https://app.gladia.io/auth/signup | 1 minute |

Your `.env` file should look like this (fill in the keys you have):

```env
GROQ_API_KEY=gsk_your_key_here
GEMINI_API_KEY=
ASSEMBLYAI_API_KEY=
DEEPGRAM_API_KEY=
GLADIA_API_KEY=
```

### 3. Start the server

```bash
uvicorn main:app --reload --port 8000
```

You should see:

```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

### 4. Verify it works

```bash
curl http://localhost:8000/health
```

You should see your configured providers:

```json
{"status": "ok", "providers_available": ["groq"]}
```

You're ready to go.

---

## Endpoints

This API has **3 endpoints**:

| Method | Path | What it does |
|---|---|---|
| `GET` | `/health` | Check if the server is running and which providers are available |
| `POST` | `/transcribe` | Transcribe a video/audio from a **URL** |
| `POST` | `/transcribe/upload` | Transcribe a video/audio from an **uploaded file** |

There is also an **interactive docs page** at `http://localhost:8000/docs` where you can test every endpoint from your browser — just fill in the fields and click Execute.

---

## How to Call Each Endpoint

### GET /health

Check if the server is up and which providers have API keys configured.

**Call it:**

```bash
curl http://localhost:8000/health
```

**Response:**

```json
{
  "status": "ok",
  "providers_available": ["groq", "assemblyai", "deepgram"]
}
```

If `providers_available` is empty, no API keys are set in `.env`.

---

### POST /transcribe

Send a video or audio URL and get back a transcript.

**Request body (JSON):**

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `video_url` | string | Yes | — | Any video or audio URL |
| `provider` | string | No | `"auto"` | Which provider to use (see [Providers](#providers)) |
| `language` | string | No | `"en"` | Language of the audio ([BCP-47 code](https://en.wikipedia.org/wiki/IETF_language_tag)) |

**Provider options:** `auto`, `groq`, `gemini`, `assemblyai`, `deepgram`, `gladia`

#### Example 1 — Basic (auto mode)

Just send a URL. The API picks the best available provider automatically.

```bash
curl -X POST http://localhost:8000/transcribe \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"}'
```

**Response:**

```json
{
  "transcript": "Alright, so here we are in front of the elephants. The cool thing about these guys is that they have really, really, really long trunks. And that's cool. And that's pretty much all there is to say.",
  "provider_used": "groq",
  "duration_seconds": 19.0,
  "processing_time_ms": 5009.6
}
```

#### Example 2 — Choose a specific provider

```bash
curl -X POST http://localhost:8000/transcribe \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
    "provider": "deepgram",
    "language": "en"
  }'
```

#### Example 3 — Non-English language

```bash
curl -X POST http://localhost:8000/transcribe \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://www.youtube.com/watch?v=VIDEO_ID",
    "language": "ur"
  }'
```

Common language codes: `en` (English), `es` (Spanish), `fr` (French), `de` (German), `ar` (Arabic), `ur` (Urdu), `hi` (Hindi), `zh` (Chinese), `ja` (Japanese), `ko` (Korean).

#### Example 4 — Direct file URL

Works with any direct link to an audio or video file:

```bash
curl -X POST http://localhost:8000/transcribe \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://example.com/podcast-episode.mp3"}'
```

#### Error responses

| HTTP Status | Error Code | Meaning |
|---|---|---|
| 400 | `BAD_REQUEST` | Bad URL, video too long, provider not configured |
| 422 | Validation Error | Missing `video_url` or invalid `provider` value |
| 429 | `RATE_LIMITED` | The chosen provider is rate limited right now |
| 502 | `ALL_PROVIDERS_FAILED` | Every provider failed (auto mode) |
| 500 | `INTERNAL_ERROR` | Something unexpected went wrong |

Error response body:

```json
{
  "error": "BAD_REQUEST",
  "message": "Video duration 7200s exceeds maximum 3600s"
}
```

---

### POST /transcribe/upload

Upload a file from your computer and get a transcript back. Use this when you have a local recording, meeting video, voice memo, etc.

**Request:** `multipart/form-data` (not JSON)

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `file` | file | Yes | — | The audio or video file |
| `provider` | string | No | `"auto"` | Which provider to use |
| `language` | string | No | `"en"` | Language of the audio |

**Supported file types:** `.mp3`, `.mp4`, `.m4a`, `.wav`, `.webm`, `.ogg`, `.flac`, `.aac`, `.mkv`, `.avi`, `.mov`, `.wmv`, `.mpeg`, `.mpga`

**Max file size:** 500 MB (configurable in `.env`)

#### Example 1 — Upload an MP3

```bash
curl -X POST http://localhost:8000/transcribe/upload \
  -F "file=@/path/to/recording.mp3"
```

**Response:** Same format as `/transcribe`:

```json
{
  "transcript": "Hello, welcome to today's meeting...",
  "provider_used": "groq",
  "duration_seconds": 342.5,
  "processing_time_ms": 8200.3
}
```

#### Example 2 — Upload a video with specific provider

```bash
curl -X POST http://localhost:8000/transcribe/upload \
  -F "file=@C:\Users\me\Videos\meeting.mp4" \
  -F "provider=assemblyai" \
  -F "language=en"
```

#### Example 3 — Upload a WAV file

```bash
curl -X POST http://localhost:8000/transcribe/upload \
  -F "file=@interview.wav"
```

#### Windows users — curl syntax

On Windows CMD, use double quotes:

```cmd
curl -X POST http://localhost:8000/transcribe/upload -F "file=@C:\Users\me\recording.mp3"
```

On Windows PowerShell, use `Invoke-RestMethod` instead (see [PowerShell examples](#powershell) below).

---

## Calling from Code

### Python

```python
import requests

BASE = "http://localhost:8000"

# --- Transcribe a URL ---
resp = requests.post(f"{BASE}/transcribe", json={
    "video_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
})
data = resp.json()
print(data["transcript"])
print(f"Provider: {data['provider_used']}, took {data['processing_time_ms']}ms")

# --- Upload a local file ---
with open("my_recording.mp3", "rb") as f:
    resp = requests.post(
        f"{BASE}/transcribe/upload",
        files={"file": ("my_recording.mp3", f, "audio/mpeg")},
        data={"provider": "auto", "language": "en"},
    )
print(resp.json()["transcript"])

# --- Upload a video file ---
with open("meeting.mp4", "rb") as f:
    resp = requests.post(
        f"{BASE}/transcribe/upload",
        files={"file": ("meeting.mp4", f, "video/mp4")},
    )
print(resp.json()["transcript"])

# --- Health check ---
resp = requests.get(f"{BASE}/health")
print(resp.json()["providers_available"])
```

### Python (async with httpx)

```python
import httpx
import asyncio

async def transcribe_url(url: str):
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post("http://localhost:8000/transcribe", json={
            "video_url": url,
        })
        return resp.json()

async def transcribe_file(file_path: str):
    async with httpx.AsyncClient(timeout=300) as client:
        with open(file_path, "rb") as f:
            resp = await client.post(
                "http://localhost:8000/transcribe/upload",
                files={"file": (file_path.split("/")[-1], f)},
            )
        return resp.json()

# Usage
result = asyncio.run(transcribe_url("https://www.youtube.com/watch?v=jNQXAC9IVRw"))
print(result["transcript"])

result = asyncio.run(transcribe_file("recording.mp3"))
print(result["transcript"])
```

### JavaScript / TypeScript

```javascript
const BASE = "http://localhost:8000";

// --- Transcribe a URL ---
const resp = await fetch(`${BASE}/transcribe`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    video_url: "https://www.youtube.com/watch?v=jNQXAC9IVRw",
  }),
});
const data = await resp.json();
console.log(data.transcript);

// --- Upload a file (browser) ---
const fileInput = document.querySelector('input[type="file"]');
const formData = new FormData();
formData.append("file", fileInput.files[0]);
formData.append("provider", "auto");
formData.append("language", "en");

const uploadResp = await fetch(`${BASE}/transcribe/upload`, {
  method: "POST",
  body: formData,
});
console.log((await uploadResp.json()).transcript);

// --- Upload a file (Node.js) ---
const fs = require("fs");
const nodeFormData = new FormData();
nodeFormData.append("file", new Blob([fs.readFileSync("recording.mp3")]), "recording.mp3");

const nodeResp = await fetch(`${BASE}/transcribe/upload`, {
  method: "POST",
  body: nodeFormData,
});
console.log((await nodeResp.json()).transcript);
```

### PowerShell

```powershell
# --- Health check ---
Invoke-RestMethod -Uri "http://localhost:8000/health"

# --- Transcribe a URL ---
$body = @{
    video_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
    provider  = "auto"
    language  = "en"
} | ConvertTo-Json

$result = Invoke-RestMethod -Uri "http://localhost:8000/transcribe" `
    -Method Post -Body $body -ContentType "application/json"
$result.transcript

# --- Upload a file ---
$form = @{
    file     = Get-Item "C:\Users\me\recording.mp3"
    provider = "auto"
    language = "en"
}
$result = Invoke-RestMethod -Uri "http://localhost:8000/transcribe/upload" `
    -Method Post -Form $form
$result.transcript
```

---

## Supported URL Types

This service uses [yt-dlp](https://github.com/yt-dlp/yt-dlp) for URL extraction, which supports **1000+ websites**. Some common ones:

| Platform | Example URL |
|---|---|
| YouTube | `https://www.youtube.com/watch?v=dQw4w9WgXcQ` |
| YouTube Shorts | `https://www.youtube.com/shorts/VIDEO_ID` |
| Twitter / X | `https://x.com/user/status/1234567890` |
| TikTok | `https://www.tiktok.com/@user/video/1234567890` |
| Vimeo | `https://vimeo.com/123456789` |
| Facebook | `https://www.facebook.com/watch/?v=123456` |
| Instagram Reel | `https://www.instagram.com/reel/ABC123/` |
| Reddit | `https://www.reddit.com/r/sub/comments/id/title/` |
| Twitch clips | `https://clips.twitch.tv/ClipName` |
| Direct file | `https://example.com/file.mp3` or `.mp4`, `.wav`, etc. |

If yt-dlp can play it, this API can transcribe it.

---

## Providers

### Provider comparison

| # | Provider | Model | Speed | Accuracy | Free Tier |
|---|---|---|---|---|---|
| 1 | **Groq** | whisper-large-v3-turbo | Fastest | Great | Generous rate limits |
| 2 | **Gemini** | gemini-2.0-flash | Fast | Good | 1,500 req/day |
| 3 | **AssemblyAI** | universal-2 | Medium | Excellent | 100 hours free |
| 4 | **Deepgram** | nova-2 | Fast | Great | $200 free credit |
| 5 | **Gladia** | Default (async) | Medium | Excellent | 10 hrs/month |

### How auto mode works

When you set `"provider": "auto"` (or just don't include the field), the API:

1. Tries **Groq** first (fastest)
2. If Groq fails or isn't configured, tries **Gemini**
3. Then **AssemblyAI**, then **Deepgram**, then **Gladia**
4. Skips any provider with no API key in `.env`
5. Skips any provider that was rate-limited in the last 5 minutes
6. Returns the result from the **first one that works**
7. If all fail, returns error `ALL_PROVIDERS_FAILED`

### Rate limiting

If a provider returns HTTP 429 (too many requests):
- It goes on a **5-minute cooldown**
- Auto mode skips it during that window
- After 5 minutes it becomes available again
- If you request a specific rate-limited provider, you get a `429` response with a message telling you to use `provider=auto` instead

---

## Configuration

All settings live in the `.env` file:

```env
# Provider API keys — add at least one
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=AIza...
ASSEMBLYAI_API_KEY=...
DEEPGRAM_API_KEY=...
GLADIA_API_KEY=...

# Max video/audio duration allowed (seconds). Default: 3600 (1 hour)
MAX_DURATION_SECONDS=3600

# Max uploaded file size (MB). Default: 500
MAX_UPLOAD_SIZE_MB=500

# Where temp audio files are stored (auto-cleaned after each request)
TEMP_DIR=/tmp/transcriber
```

---

## Project Structure

```
transcriber/
├── main.py                    # FastAPI app — all 3 endpoints
├── config.py                  # Loads settings from .env
├── models.py                  # Request/response data shapes
├── audio_extractor.py         # Downloads audio (yt-dlp) + converts (FFmpeg)
├── provider_router.py         # Picks which provider to use, handles fallback
├── providers/
│   ├── base.py                # Interface all providers implement
│   ├── groq_provider.py       # Groq — whisper-large-v3-turbo
│   ├── gemini_provider.py     # Google Gemini — 2.0-flash
│   ├── assemblyai_provider.py # AssemblyAI — universal-2
│   ├── deepgram_provider.py   # Deepgram — nova-2
│   └── gladia_provider.py     # Gladia — REST v2 with polling
├── .env                       # Your API keys (not committed to git)
├── .env.example               # Template showing all settings
├── requirements.txt           # Python dependencies with pinned versions
└── README.md                  # This file
```

---

## Troubleshooting

| Problem | What to do |
|---|---|
| `"providers_available": []` | No API keys in `.env`. Add at least one key and restart the server. |
| `ALL_PROVIDERS_FAILED` | Your API keys might be invalid or expired. Check the server terminal for detailed error logs. |
| `RATE_LIMITED` | That provider has hit its free tier limit. Use `"provider": "auto"` to automatically try the next one, or wait 5 minutes. |
| `BAD_REQUEST: Video duration Xs exceeds maximum Ys` | Video is too long. Increase `MAX_DURATION_SECONDS` in `.env` and restart. |
| `BAD_REQUEST: Unsupported file type` | Upload endpoint only accepts audio/video files. See the supported types list above. |
| `BAD_REQUEST: File too large` | File exceeds 500 MB. Increase `MAX_UPLOAD_SIZE_MB` in `.env` or compress the file first. |
| `Live streams are not supported` | This API only handles pre-recorded content, not live streams. |
| Server starts but first request is slow | On first run, `static-ffmpeg` downloads the FFmpeg binary (~30 MB). Subsequent requests are fast. |
| `ModuleNotFoundError` | Make sure you activated the virtual environment (`venv\Scripts\activate` on Windows) before running. |
| Can't connect to `localhost:8000` | Make sure the server is running (`uvicorn main:app --reload --port 8000`). |
