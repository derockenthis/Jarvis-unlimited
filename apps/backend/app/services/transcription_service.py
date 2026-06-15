from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict

from app.config import Settings


class SpeechToTextService:
    """Transcribe audio with configurable model (local mlx-whisper or OpenRouter)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def transcribe_audio(
        self,
        audio_bytes: bytes,
        filename: str,
        content_type: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        # Use provided model or fall back to configured default
        speech_model = model or self.settings.local_whisper_model

        # Route to OpenRouter if model is prefixed with openrouter/
        if speech_model.startswith("openrouter/"):
            return self._transcribe_openrouter(audio_bytes, filename, speech_model)

        # Otherwise use local mlx-whisper
        return self._transcribe_local(audio_bytes, filename, speech_model)

    def _transcribe_local(
        self, audio_bytes: bytes, filename: str, model: str
    ) -> dict[str, Any]:
        try:
            import mlx_whisper
        except ImportError:
            return {
                "status": "error",
                "error": (
                    "mlx-whisper is not installed. "
                    "Run: pip install mlx-whisper (or uv add mlx-whisper) to enable local speech transcription."
                ),
            }

        try:
            result = self._transcribe_locally(mlx_whisper, audio_bytes, filename, model)
            text = result["text"].strip()
            if not text:
                return {
                    "status": "error",
                    "error": "No transcription text was returned.",
                }

            return {
                "status": "success",
                "data": {
                    "text": text,
                    "model": model,
                },
            }
        except Exception as error:  # noqa: BLE001
            return {"status": "error", "error": str(error)}

    def _transcribe_openrouter(
        self, audio_bytes: bytes, filename: str, model: str
    ) -> dict[str, Any]:
        try:
            import httpx
        except ImportError:
            return {
                "status": "error",
                "error": "httpx is not installed. Run: pip install httpx",
            }

        api_key = self.settings.openrouter_api_key
        if not api_key:
            return {
                "status": "error",
                "error": "OpenRouter API key not configured. Set OPENROUTER_API_KEY.",
            }

        base_url = self.settings.openrouter_base_url or "https://openrouter.ai/api/v1"
        model_slug = model.removeprefix("openrouter/")

        try:
            suffix = Path(filename).suffix.lower()
            if not suffix:
                suffix = ".webm"

            with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
                tmp.write(audio_bytes)
                tmp.flush()

                with httpx.Client(timeout=60.0) as client:
                    with open(tmp.name, "rb") as audio_file:
                        files = {"file": (tmp.name, audio_file, "audio/webm")}
                        data = {"model": model_slug}
                        headers = {"Authorization": f"Bearer {api_key}"}
                        response = client.post(
                            f"{base_url}/audio/transcriptions",
                            files=files,
                            data=data,
                            headers=headers,
                        )

            if response.status_code != 200:
                return {
                    "status": "error",
                    "error": f"OpenRouter transcription failed: {response.text}",
                }

            result = response.json()
            text = result.get("text", "").strip()
            if not text:
                return {
                    "status": "error",
                    "error": "No transcription text was returned.",
                }

            return {
                "status": "success",
                "data": {
                    "text": text,
                    "model": model,
                },
            }
        except Exception as error:  # noqa: BLE001
            return {"status": "error", "error": str(error)}

    def _transcribe_locally(
        self, mlx_whisper: object, audio_bytes: bytes, filename: str, model: str
    ) -> Dict[str, Any]:
        suffix = Path(filename).suffix.lower()
        if not suffix:
            suffix = ".webm"

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
            tmp.write(audio_bytes)
            tmp.flush()
            return mlx_whisper.transcribe(
                tmp.name,
                path_or_hf_repo=model,
            )