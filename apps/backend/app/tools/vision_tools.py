from collections.abc import Callable
from typing import Any

from app.security.path_policy import PathPolicy
from app.services.desktop_vision_service import DesktopVisionService


def build_vision_tools(
    desktop_vision_service: DesktopVisionService, policy: PathPolicy
) -> list[Callable[..., dict[str, Any]]]:
    """Build screenshot and image-analysis tools."""

    def capture_desktop_screenshot_tool(name: str) -> dict[str, Any]:
        """Capture the current macOS desktop into the app screenshot directory.

        Args:
            name: Filename stem for the screenshot.

        Returns:
            A dictionary with the saved screenshot path.
        """

        return desktop_vision_service.capture_desktop_screenshot(name)

    def analyze_image_tool(path: str, prompt: str) -> dict[str, Any]:
        """Analyze a local image or screenshot with the configured vision model.

        Args:
            path: Absolute path of the image file to analyze.
            prompt: What the agent should look for in the image.

        Returns:
            A dictionary with the model's analysis.
        """

        return desktop_vision_service.analyze_image(path, prompt, policy)

    return [capture_desktop_screenshot_tool, analyze_image_tool]