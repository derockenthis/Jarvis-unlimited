from collections.abc import Callable
from typing import Any

from app.services.memory_service import MemoryService


def build_memory_tools(memory_service: MemoryService) -> list[Callable[..., dict[str, Any]]]:
    """Build lightweight tools over the durable memory store."""

    def memory_status_tool() -> dict[str, Any]:
        """Return the current NBAM storage status.

        Returns:
            A dictionary with memory root, node ids, node count, and observation count.
        """

        return memory_service.status()

    def read_memory_node_tool(node_id: str) -> dict[str, Any]:
        """Read a durable memory node by id.

        Args:
            node_id: Memory node id without the `.md` suffix.

        Returns:
            A dictionary with the node content when the node exists.
        """

        return memory_service.read_node(node_id)

    return [memory_status_tool, read_memory_node_tool]