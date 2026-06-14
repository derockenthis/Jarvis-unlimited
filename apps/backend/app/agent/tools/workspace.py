from collections.abc import Callable
from typing import Any

from app.security.path_policy import PathPolicy
from app.tools.agent_tools import build_agent_tools


def build_workspace_tools(policy: PathPolicy) -> list[Callable[..., dict[str, Any]]]:
    """Return the workspace and file-editing tools exposed to the root agent."""

    return build_agent_tools(policy)