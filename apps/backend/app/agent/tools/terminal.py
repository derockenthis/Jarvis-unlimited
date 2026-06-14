from collections.abc import Callable
from typing import Any

from app.security.path_policy import PathPolicy
from app.services.session_terminal_service import SessionTerminalService
from app.tools.terminal_tools import build_terminal_tools as build_bound_terminal_tools


def build_terminal_tools(
    terminal_service: SessionTerminalService,
    policy: PathPolicy,
    user_id: str,
    session_id: str,
) -> list[Callable[..., dict[str, Any]]]:
    """Return terminal tools bound to the current chat session."""

    return build_bound_terminal_tools(terminal_service, policy, user_id, session_id)