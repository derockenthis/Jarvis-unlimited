import base64
import mimetypes
import re
import subprocess
from typing import Any

from litellm import completion

from app.config import Settings
from app.security.path_policy import PathPolicy


class DesktopVisionService:
    """Capture desktop screenshots and analyze local images with a vision model."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def capture_desktop_screenshot(self, name: str) -> dict[str, Any]:
        screenshot_dir = self.settings.screenshot_dir.expanduser().resolve()
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "-", name).strip("-") or "desktop"
        target = screenshot_dir / f"{safe_name}.png"
        completed = subprocess.run(
            ["screencapture", "-x", str(target)],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        if completed.returncode != 0:
            return {
                "status": "error",
                "error": completed.stderr.strip() or "Failed to capture desktop screenshot.",
            }
        return {"status": "success", "data": {"path": str(target), "name": target.name}}

    def analyze_image(self, path: str, prompt: str, policy: PathPolicy) -> dict[str, Any]:
        try:
            target = policy.resolve_allowed(path)
            if not target.is_file():
                return {"status": "error", "error": "Image path is not a file."}
            mime_type, _ = mimetypes.guess_type(target.name)
            mime_type = mime_type or "image/png"
            encoded = base64.b64encode(target.read_bytes()).decode("ascii")
            response = completion(
                model=self.settings.openrouter_litellm_vision_model,
                api_key=self.settings.openrouter_api_key,
                api_base=self.settings.openrouter_base_url,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
                            },
                        ],
                    }
                ],
            )
            message = response.choices[0].message.content if response.choices else ""
            return {
                "status": "success",
                "data": {"path": str(target), "analysis": message or "No analysis returned."},
            }
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "error": str(exc)}