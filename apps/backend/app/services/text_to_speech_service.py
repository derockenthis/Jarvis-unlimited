from __future__ import annotations

import io
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from app.config import Settings


class TextToSpeechService:
    """Generate spoken audio with a local neural model when available."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def synthesize_speech(self, text: str) -> dict[str, Any]:
        content = text.strip()
        if not content:
            return {
                "status": "error",
                "error": "No text was provided for speech synthesis.",
            }

        neural_result = self._synthesize_with_kokoro(content)
        if neural_result["status"] == "success":
            return neural_result

        fallback_result = self._synthesize_with_pyttsx3(content)
        if fallback_result["status"] == "success":
            return fallback_result

        return neural_result if neural_result.get("error") else fallback_result

    def _synthesize_with_kokoro(self, text: str) -> dict[str, Any]:
        try:
            import soundfile as sf
            from kokoro import KPipeline
        except ImportError as error:
            return {
                "status": "error",
                "error": (
                    "Kokoro TTS is not installed. Install `kokoro` and `soundfile` "
                    "to enable neural local speech synthesis."
                ),
                "details": str(error),
            }

        voice = self.settings.local_tts_voice
        sample_rate = self.settings.local_tts_sample_rate

        try:
            pipeline = KPipeline(lang_code=self.settings.local_tts_language_code)
            audio_segments: list[np.ndarray] = []

            for chunk in pipeline(text, voice=voice):
                audio = None
                if isinstance(chunk, tuple):
                    if len(chunk) >= 3:
                        audio = chunk[2]
                    elif chunk:
                        audio = chunk[-1]
                elif hasattr(chunk, "audio"):
                    audio = getattr(chunk, "audio")

                if audio is None:
                    continue

                segment = np.asarray(audio, dtype=np.float32).reshape(-1)
                if segment.size > 0:
                    audio_segments.append(segment)

            if not audio_segments:
                return {
                    "status": "error",
                    "error": "Kokoro did not return any audio segments.",
                }

            merged = np.concatenate(audio_segments)
            buffer = io.BytesIO()
            sf.write(buffer, merged, sample_rate, format="WAV")
            return {
                "status": "success",
                "data": {
                    "audio_bytes": buffer.getvalue(),
                    "content_type": "audio/wav",
                    "provider": "kokoro",
                    "voice": voice,
                },
            }
        except Exception as error:  # noqa: BLE001
            return {
                "status": "error",
                "error": f"Neural TTS synthesis failed: {error}",
            }

    def _synthesize_with_pyttsx3(self, text: str) -> dict[str, Any]:
        try:
            import pyttsx3
        except ImportError as error:
            return {
                "status": "error",
                "error": (
                    "pyttsx3 is not installed. Install `pyttsx3` to enable local fallback speech synthesis."
                ),
                "details": str(error),
            }

        output_path: Path | None = None
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", self.settings.local_tts_rate)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                output_path = Path(tmp.name)
            engine.save_to_file(text, str(output_path))
            engine.runAndWait()
            audio_bytes = output_path.read_bytes()
            return {
                "status": "success",
                "data": {
                    "audio_bytes": audio_bytes,
                    "content_type": "audio/wav",
                    "provider": "pyttsx3",
                    "voice": "",
                },
            }
        except Exception as error:  # noqa: BLE001
            return {
                "status": "error",
                "error": f"Fallback speech synthesis failed: {error}",
            }
        finally:
            if output_path and output_path.exists():
                try:
                    output_path.unlink()
                except OSError:
                    pass
