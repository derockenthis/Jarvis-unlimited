from collections.abc import Callable
from typing import Any

from app.services.memory_service import MemoryService
from app.tools.memory_tools import build_memory_tools as build_bound_memory_tools


def build_memory_tools(memory_service: MemoryService) -> list[Callable[..., dict[str, Any]]]:
    """Return durable-memory tools exposed to the root agent."""

    return build_bound_memory_tools(memory_service)