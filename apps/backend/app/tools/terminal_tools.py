from collections.abc import Callable
from typing import Any

from app.security.path_policy import PathPolicy
from app.services.session_terminal_service import SessionTerminalService


def build_terminal_tools(
    terminal_service: SessionTerminalService,
    policy: PathPolicy,
    user_id: str,
    session_id: str,
) -> list[Callable[..., dict[str, Any]]]:
    """Build ADK terminal tools bound to the current chat session."""

    def terminal_spawn_tool(cwd: str) -> dict[str, Any]:
        """Create a persistent terminal session at a directory.

        Args:
            cwd: Absolute directory path where the terminal should start.

        Returns:
            A dictionary with ``status`` and ``data.terminal_id`` on success.
        """

        return terminal_service.spawn(
            user_id=user_id, session_id=session_id, cwd=cwd, path_policy=policy
        )

    def terminal_run_tool(terminal_id: str, command: str) -> dict[str, Any]:
        """Run an allowed command in a persistent terminal session.

        Args:
            terminal_id: Terminal session id returned by ``terminal_spawn_tool``.
            command: Command string to run without shell operators.

        Returns:
            A dictionary with ``status`` and captured stdout, stderr, return code, and cwd.
        """

        return terminal_service.run(
            user_id=user_id,
            session_id=session_id,
            terminal_id=terminal_id,
            command=command,
            path_policy=policy,
        )

    def terminal_read_tool(terminal_id: str) -> dict[str, Any]:
        """Read the last command result from a persistent terminal session.

        Args:
            terminal_id: Terminal session id returned by ``terminal_spawn_tool``.

        Returns:
            A dictionary with the terminal cwd and last command result.
        """

        return terminal_service.read(
            user_id=user_id, session_id=session_id, terminal_id=terminal_id
        )

    def terminal_close_tool(terminal_id: str) -> dict[str, Any]:
        """Close a persistent terminal session.

        Args:
            terminal_id: Terminal session id returned by ``terminal_spawn_tool``.

        Returns:
            A dictionary with ``status`` describing whether the terminal was closed.
        """

        return terminal_service.close(
            user_id=user_id, session_id=session_id, terminal_id=terminal_id
        )

    return [terminal_spawn_tool, terminal_run_tool, terminal_read_tool, terminal_close_tool]