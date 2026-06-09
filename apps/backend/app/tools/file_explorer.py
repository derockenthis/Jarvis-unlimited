from pathlib import Path

from app.security.path_policy import PathPolicy
from app.tools.models import ToolResult


def list_directory(path: str, policy: PathPolicy) -> ToolResult:
    """List immediate children for a directory inside an allowed workspace root."""

    try:
        directory = policy.resolve_allowed(path)
        if not directory.is_dir():
            return ToolResult(status="error", error="Path is not a directory.")

        children = []
        for child in sorted(directory.iterdir(), key=lambda item: item.name.lower()):
            if child.name in {".git", "node_modules", "__pycache__", ".venv"}:
                continue
            stat = child.stat()
            children.append(
                {
                    "name": child.name,
                    "path": str(child),
                    "type": "directory" if child.is_dir() else "file",
                    "size": stat.st_size,
                }
            )
        return ToolResult(status="success", data={"path": str(directory), "children": children})
    except Exception as exc:  # noqa: BLE001 - surfaced as structured tool failure
        return ToolResult(status="error", error=str(exc))


def folder_tree(path: str, max_depth: int, max_entries: int, policy: PathPolicy) -> ToolResult:
    """Return a bounded recursive tree for a directory inside an allowed workspace root."""

    try:
        root = policy.resolve_allowed(path)
        entries: list[dict[str, object]] = []

        def visit(current: Path, depth: int) -> None:
            if len(entries) >= max_entries or depth > max_depth:
                return
            for child in sorted(current.iterdir(), key=lambda item: item.name.lower()):
                if len(entries) >= max_entries:
                    return
                if child.name in {".git", "node_modules", "__pycache__", ".venv"}:
                    continue
                entries.append(
                    {
                        "path": str(child),
                        "name": child.name,
                        "depth": depth,
                        "type": "directory" if child.is_dir() else "file",
                    }
                )
                if child.is_dir():
                    visit(child, depth + 1)

        visit(root, 1)
        return ToolResult(status="success", data={"root": str(root), "entries": entries})
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))
