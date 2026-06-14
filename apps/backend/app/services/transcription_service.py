from __future__ import annotations

import importlib
import mimetypes
from pathlib import Path
import shutil
import tempfile
from typing import Any

from app.config import Settings


class SpeechToTextService:
    """Transcribe audio with a local MLX Whisper model."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def transcribe_audio(
        self,
        audio_bytes: bytes,
        filename: str,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        if shutil.which("ffmpeg") is None:
            return {
                "status": "error",
                "error": "Local speech transcription requires ffmpeg. Install it with `brew install ffmpeg`.",
            }

        target_name = Path(filename).name or "speech.webm"
        mime_type = content_type or mimetypes.guess_type(target_name)[0] or "audio/webm"
        suffix = self._audio_suffix_from(target_name, mime_type)

        try:
            mlx_whisper = self._load_mlx_whisper()
            with tempfile.NamedTemporaryFile(suffix=f".{suffix}", delete=False) as audio_file:
                audio_file.write(audio_bytes)
                audio_path = Path(audio_file.name)

            try:
                response_payload = mlx_whisper.transcribe(
                    str(audio_path),
                    path_or_hf_repo=self.settings.speech_to_text_model,
                )
            finally:
                audio_path.unlink(missing_ok=True)

            text = str(response_payload.get("text", "")).strip()
            if not text:
                return {
                    "status": "error",
                    "error": "No transcription text was returned.",
                }

            model = str(response_payload.get("model") or self.settings.speech_to_text_model)
            return {
                "status": "success",
                "data": {
                    "text": text,
                    "model": model,
                },
            }
        except ModuleNotFoundError:
            return {
                "status": "error",
                "error": "Local speech transcription requires the `mlx-whisper` Python package. Install it in `apps/backend` with `uv add mlx-whisper`.",
            }
        except Exception as error:  # noqa: BLE001
            return {"status": "error", "error": str(error)}

    def _load_mlx_whisper(self) -> Any:
        return importlib.import_module("mlx_whisper")

    def _audio_suffix_from(self, filename: str, mime_type: str) -> str:
        suffix = Path(filename).suffix.lower().lstrip(".")
        if suffix in {"wav", "mp3", "m4a", "webm", "ogg", "flac"}:
            return suffix

        guessed = mimetypes.guess_extension(mime_type or "")
        if guessed:
            guessed_suffix = guessed.lstrip(".").lower()
            if guessed_suffix in {"wav", "mp3", "m4a", "webm", "ogg", "flac"}:
                return guessed_suffix

        return "webm"