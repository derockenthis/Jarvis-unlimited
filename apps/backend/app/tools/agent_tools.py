"""ADK-compatible tool wrappers.

The underlying tool functions in this package take a ``PathPolicy`` argument so they can be unit
tested in isolation. ADK FunctionTools must expose only model-facing parameters, so these wrappers
close over a single ``PathPolicy`` instance and return plain dictionaries.
"""

from collections.abc import Callable
from typing import Any

from app.agent.tools.cli import build_cli_agent_tools
from app.security.path_policy import PathPolicy
from app.tools.edit_tools import create_file, insert_at_line, replace_file_section
from app.tools.file_explorer import folder_tree, list_directory
from app.tools.search_tools import read_file_section, ripgrep_search


def build_agent_tools(policy: PathPolicy) -> list[Callable[..., dict[str, Any]]]:
    """Build the list of ADK tool callables bound to a path policy."""

    def list_directory_tool(path: str) -> dict[str, Any]:
        """List the immediate files and folders inside a directory.

        Args:
            path: Absolute path of the directory to inspect.

        Returns:
            A dictionary with ``status`` and, on success, ``data.children`` describing each entry.
        """

        return list_directory(path, policy).model_dump()

    def folder_tree_tool(path: str, max_depth: int, max_entries: int) -> dict[str, Any]:
        """Return a bounded recursive tree of a directory.

        Args:
            path: Absolute path of the directory to walk.
            max_depth: Maximum directory depth to descend into.
            max_entries: Maximum number of entries to return.

        Returns:
            A dictionary with ``status`` and, on success, ``data.entries`` listing each node.
        """

        return folder_tree(path, max_depth, max_entries, policy).model_dump()

    def read_file_section_tool(path: str, start_line: int, end_line: int) -> dict[str, Any]:
        """Read a bounded line range from a text file.

        Args:
            path: Absolute path of the file to read.
            start_line: First line to read, 1-based and inclusive.
            end_line: Last line to read, 1-based and inclusive.

        Returns:
            A dictionary with ``status`` and, on success, ``data.content`` holding the text.
        """

        return read_file_section(path, start_line, end_line, policy).model_dump()

    def search_files_tool(query: str, root: str, max_results: int) -> dict[str, Any]:
        """Search file contents recursively using ripgrep.

        Args:
            query: The text or regular expression to search for.
            root: Absolute path of the directory to search within.
            max_results: Maximum number of matching lines to return.

        Returns:
            A dictionary with ``status`` and, on success, ``data.matches`` listing each hit.
        """

        return ripgrep_search(query, root, max_results, policy).model_dump()

    def create_file_tool(path: str, content: str, overwrite: bool) -> dict[str, Any]:
        """Create or overwrite a text file with the given content.

        Args:
            path: Absolute path of the file to write.
            content: Full text content to write into the file.
            overwrite: Whether to overwrite the file if it already exists.

        Returns:
            A dictionary with ``status`` and, on success, ``diff`` showing the change.
        """

        return create_file(path, content, overwrite, policy).model_dump()

    def replace_file_section_tool(
        path: str, start_line: int, end_line: int, replacement: str
    ) -> dict[str, Any]:
        """Replace a bounded line range in a text file with new content.

        Args:
            path: Absolute path of the file to edit.
            start_line: First line to replace, 1-based and inclusive.
            end_line: Last line to replace, 1-based and inclusive.
            replacement: Text to insert in place of the removed lines.

        Returns:
            A dictionary with ``status`` and, on success, ``diff`` showing the change.
        """

        return replace_file_section(path, start_line, end_line, replacement, policy).model_dump()

    def insert_at_line_tool(path: str, line: int, content: str) -> dict[str, Any]:
        """Insert text before a given line in a text file.

        Args:
            path: Absolute path of the file to edit.
            line: Line number to insert before, 1-based.
            content: Text to insert at the given position.

        Returns:
            A dictionary with ``status`` and, on success, ``diff`` showing the change.
        """

        return insert_at_line(path, line, content, policy).model_dump()

    return [
        list_directory_tool,
        folder_tree_tool,
        read_file_section_tool,
        search_files_tool,
        create_file_tool,
        replace_file_section_tool,
        insert_at_line_tool,
        *build_cli_agent_tools(policy),
    ]
