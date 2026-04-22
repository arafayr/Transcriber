import asyncio
import glob as globmod
import os
import subprocess
import uuid
import math
import logging
from dataclasses import dataclass
#new file
import static_ffmpeg
static_ffmpeg.add_paths()

import yt_dlp

from config import get_settings

logger = logging.getLogger(__name__)

MAX_GROQ_FILE_SIZE = 25 * 1024 * 1024  # 25 MB


@dataclass
class ExtractedAudio:
    file_path: str
    duration_seconds: float
    title: str


class AudioExtractor:
    def __init__(self):
        settings = get_settings()
        self.temp_dir = settings.temp_dir
        self.max_duration = settings.max_duration_seconds
        os.makedirs(self.temp_dir, exist_ok=True)

    async def extract(self, video_url: str) -> ExtractedAudio:
        return await asyncio.to_thread(self._extract_sync, video_url)

    def _extract_sync(self, video_url: str) -> ExtractedAudio:
        info = self._get_info(video_url)
        duration = info.get("duration") or 0
        title = info.get("title", "unknown")

        if duration > self.max_duration:
            raise ValueError(
                f"Video duration {duration}s exceeds maximum {self.max_duration}s"
            )

        job_id = uuid.uuid4().hex[:12]
        output_path = os.path.join(self.temp_dir, f"{job_id}.%(ext)s")

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": output_path,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "128",
                }
            ],
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        mp3_path = os.path.join(self.temp_dir, f"{job_id}.mp3")
        if not os.path.exists(mp3_path):
            matches = globmod.glob(os.path.join(self.temp_dir, f"{job_id}.*"))
            if matches:
                mp3_path = matches[0]

        if not os.path.exists(mp3_path):
            raise RuntimeError("Audio extraction failed — no output file found")

        if not duration:
            duration = self._probe_duration(mp3_path)
            if duration > self.max_duration:
                self.cleanup(mp3_path)
                raise ValueError(
                    f"Audio duration {duration:.0f}s exceeds maximum {self.max_duration}s"
                )

        return ExtractedAudio(
            file_path=mp3_path,
            duration_seconds=duration,
            title=title,
        )

    def _get_info(self, url: str) -> dict:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info and info.get("_type") == "playlist":
                entries = info.get("entries", [])
                if entries:
                    info = entries[0]
            if info and info.get("is_live"):
                raise ValueError("Live streams are not supported")
            return info

    async def save_upload(self, file_data: bytes, filename: str) -> ExtractedAudio:
        return await asyncio.to_thread(self._save_upload_sync, file_data, filename)

    def _save_upload_sync(self, file_data: bytes, filename: str) -> ExtractedAudio:
        job_id = uuid.uuid4().hex[:12]
        ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
        raw_path = os.path.join(self.temp_dir, f"{job_id}_raw.{ext}")

        with open(raw_path, "wb") as f:
            f.write(file_data)

        mp3_path = os.path.join(self.temp_dir, f"{job_id}.mp3")
        try:
            cmd = [
                "ffmpeg", "-y", "-i", raw_path,
                "-vn", "-ar", "44100", "-ac", "1", "-b:a", "128k",
                mp3_path,
            ]
            subprocess.run(cmd, capture_output=True, check=True)
        except subprocess.CalledProcessError as e:
            self.cleanup(raw_path)
            raise ValueError(
                f"FFmpeg could not process this file. Make sure it contains audio. "
                f"stderr: {e.stderr.decode(errors='replace')[:200]}"
            )

        self.cleanup(raw_path)

        duration = self._probe_duration(mp3_path)
        if duration > self.max_duration:
            self.cleanup(mp3_path)
            raise ValueError(
                f"Audio duration {duration:.0f}s exceeds maximum {self.max_duration}s"
            )

        title = filename.rsplit(".", 1)[0] if "." in filename else filename

        return ExtractedAudio(
            file_path=mp3_path,
            duration_seconds=duration,
            title=title,
        )

    @staticmethod
    def _probe_duration(file_path: str) -> float:
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", file_path],
                capture_output=True, text=True, check=True,
            )
            return float(result.stdout.strip())
        except Exception:
            return 0

    def resample_to_wav(self, input_path: str) -> str:
        wav_path = input_path.rsplit(".", 1)[0] + "_16k.wav"
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-ar", "16000", "-ac", "1", "-f", "wav", wav_path,
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return wav_path

    def split_audio(self, input_path: str, max_bytes: int = MAX_GROQ_FILE_SIZE - 1024 * 1024) -> list[str]:
        file_size = os.path.getsize(input_path)
        if file_size <= max_bytes:
            return [input_path]

        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", input_path],
            capture_output=True, text=True, check=True,
        )
        total_duration = float(result.stdout.strip())
        num_chunks = math.ceil(file_size / max_bytes)
        chunk_duration = total_duration / num_chunks

        chunks = []
        base = input_path.rsplit(".", 1)[0]
        ext = input_path.rsplit(".", 1)[1]

        for i in range(num_chunks):
            start = i * chunk_duration
            chunk_path = f"{base}_chunk{i}.{ext}"
            cmd = [
                "ffmpeg", "-y", "-i", input_path,
                "-ss", str(start), "-t", str(chunk_duration),
                "-c", "copy", chunk_path,
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            chunks.append(chunk_path)

        return chunks

    @staticmethod
    def cleanup(*paths: str):
        for p in paths:
            try:
                if p and os.path.exists(p):
                    os.remove(p)
            except OSError:
                logger.warning("Failed to delete temp file: %s", p)
