from __future__ import annotations

import base64
import json
import mimetypes
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from app.config import Settings


class SpeechToTextService:
    """Transcribe audio with the configured OpenRouter speech model."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def transcribe_audio(
        self,
        audio_bytes: bytes,
        filename: str,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        if not self.settings.openrouter_api_key:
            return {
                "status": "error",
                "error": "OpenRouter is not configured. Set OPENROUTER_API_KEY to enable speech transcription.",
            }

        target_name = Path(filename).name or "speech.webm"
        mime_type = content_type or mimetypes.guess_type(target_name)[0] or "audio/webm"

        try:
            response_payload = self._post_transcription(audio_bytes, target_name, mime_type)
            text = str(response_payload.get("text", "")).strip()
            if not text:
                return {
                    "status": "error",
                    "error": "No transcription text was returned.",
                }

            model = str(response_payload.get("model") or self.settings.openrouter_transcription_model_slug)
            return {
                "status": "success",
                "data": {
                    "text": text,
                    "model": model,
                },
            }
        except urllib.error.HTTPError as error:
            error_body = error.read().decode("utf-8", errors="ignore")
            try:
                payload = json.loads(error_body)
            except json.JSONDecodeError:
                payload = {}

            message = (
                payload.get("error", {}).get("message")
                or payload.get("message")
                or error_body.strip()
                or error.reason
                or "Speech transcription failed."
            )
            return {"status": "error", "error": message}
        except Exception as error:  # noqa: BLE001
            return {"status": "error", "error": str(error)}

    def _post_transcription(self, audio_bytes: bytes, filename: str, mime_type: str) -> dict[str, Any]:
        encoded_audio = base64.b64encode(audio_bytes).decode("utf-8")
        payload = {
            "model": self.settings.openrouter_transcription_model_slug,
            "input_audio": {
                "data": encoded_audio,
                "format": self._audio_format_from(filename, mime_type),
            },
        }

        request = urllib.request.Request(
            f"{self.settings.openrouter_base_url.rstrip('/')}/audio/transcriptions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=60) as response:
            response_body = response.read().decode("utf-8")
        return json.loads(response_body)

    def _audio_format_from(self, filename: str, mime_type: str) -> str:
        suffix = Path(filename).suffix.lower().lstrip(".")
        if suffix in {"wav", "mp3", "m4a", "webm", "ogg", "flac"}:
            return suffix

        guessed = mimetypes.guess_extension(mime_type or "")
        if guessed:
            guessed_suffix = guessed.lstrip(".").lower()
            if guessed_suffix in {"wav", "mp3", "m4a", "webm", "ogg", "flac"}:
                return guessed_suffix

        return "webm"