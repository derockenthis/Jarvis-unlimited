import shutil
import subprocess

from app.security.path_policy import PathPolicy
from app.tools.models import ToolResult


def read_file_section(path: str, start_line: int, end_line: int, policy: PathPolicy) -> ToolResult:
    """Read a bounded line range from a text file inside an allowed workspace root."""

    try:
        target = policy.resolve_allowed(path)
        if not target.is_file():
            return ToolResult(status="error", error="Path is not a file.")
        if start_line < 1 or end_line < start_line:
            return ToolResult(status="error", error="Invalid line range.")
        if target.stat().st_size > 1_000_000:
            return ToolResult(status="error", error="File is too large to read through this tool.")

        data = target.read_bytes()
        if b"\x00" in data[:4096]:
            return ToolResult(status="error", error="Binary files are not supported.")

        lines = data.decode("utf-8", errors="replace").splitlines()
        selected = lines[start_line - 1 : end_line]
        return ToolResult(
            status="success",
            data={
                "path": str(target),
                "start_line": start_line,
                "end_line": min(end_line, len(lines)),
                "content": "\n".join(selected),
            },
        )
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def ripgrep_search(query: str, root: str, max_results: int, policy: PathPolicy) -> ToolResult:
    """Search files with ripgrep inside an allowed workspace root."""

    rg_path = shutil.which("rg")
    if rg_path is None:
        return ToolResult(
            status="error",
            error="ripgrep is not installed. Install rg from https://github.com/BurntSushi/ripgrep.",
        )

    try:
        search_root = policy.resolve_allowed(root)
        command = [
            rg_path,
            "--line-number",
            "--column",
            "--with-filename",
            "--color",
            "never",
            "--max-count",
            str(max_results),
            query,
            str(search_root),
        ]
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if completed.returncode not in {0, 1}:
            return ToolResult(status="error", error=completed.stderr.strip() or "ripgrep failed.")

        matches = completed.stdout.splitlines()[:max_results]
        return ToolResult(status="success", data={"matches": matches})
    except subprocess.TimeoutExpired:
        return ToolResult(status="error", error="ripgrep search timed out.")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))
