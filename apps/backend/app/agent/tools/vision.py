from collections.abc import Callable
from typing import Any

from app.security.path_policy import PathPolicy
from app.services.desktop_vision_service import DesktopVisionService
from app.tools.vision_tools import build_vision_tools as build_bound_vision_tools


def build_vision_tools(
    desktop_vision_service: DesktopVisionService, policy: PathPolicy
) -> list[Callable[..., dict[str, Any]]]:
    """Return screen-capture and image-analysis tools."""

    return build_bound_vision_tools(desktop_vision_service, policy)