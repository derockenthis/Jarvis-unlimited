from difflib import unified_diff

from app.security.path_policy import PathPolicy
from app.tools.models import ToolResult


def create_file(path: str, content: str, overwrite: bool, policy: PathPolicy) -> ToolResult:
    """Create a text file inside an allowed workspace root."""

    try:
        target = policy.resolve_allowed(path)
        if target.exists() and not overwrite:
            return ToolResult(status="error", error="File already exists.")
        target.parent.mkdir(parents=True, exist_ok=True)
        before = target.read_text(encoding="utf-8") if target.exists() else ""
        target.write_text(content, encoding="utf-8")
        diff = "\n".join(
            unified_diff(
                before.splitlines(),
                content.splitlines(),
                fromfile=f"before/{target.name}",
                tofile=f"after/{target.name}",
                lineterm="",
            )
        )
        return ToolResult(status="success", data={"path": str(target)}, diff=diff)
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def replace_file_section(
    path: str,
    start_line: int,
    end_line: int,
    replacement: str,
    policy: PathPolicy,
) -> ToolResult:
    """Replace a bounded line range in a text file inside an allowed workspace root."""

    try:
        target = policy.resolve_allowed(path)
        before_lines = target.read_text(encoding="utf-8").splitlines()
        if start_line < 1 or end_line < start_line or end_line > len(before_lines):
            return ToolResult(status="error", error="Invalid line range.")

        replacement_lines = replacement.splitlines()
        after_lines = before_lines[: start_line - 1] + replacement_lines + before_lines[end_line:]
        diff = "\n".join(
            unified_diff(
                before_lines,
                after_lines,
                fromfile=f"before/{target.name}",
                tofile=f"after/{target.name}",
                lineterm="",
            )
        )
        target.write_text("\n".join(after_lines) + "\n", encoding="utf-8")
        return ToolResult(status="success", data={"path": str(target)}, diff=diff)
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def insert_at_line(path: str, line: int, content: str, policy: PathPolicy) -> ToolResult:
    """Insert text before a line in a text file inside an allowed workspace root."""

    try:
        target = policy.resolve_allowed(path)
        before_lines = target.read_text(encoding="utf-8").splitlines()
        if line < 1 or line > len(before_lines) + 1:
            return ToolResult(status="error", error="Invalid insert line.")

        content_lines = content.splitlines()
        after_lines = before_lines[: line - 1] + content_lines + before_lines[line - 1 :]
        diff = "\n".join(
            unified_diff(
                before_lines,
                after_lines,
                fromfile=f"before/{target.name}",
                tofile=f"after/{target.name}",
                lineterm="",
            )
        )
        target.write_text("\n".join(after_lines) + "\n", encoding="utf-8")
        return ToolResult(status="success", data={"path": str(target)}, diff=diff)
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))
