from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
import json
import os
import re
import subprocess
import sys
import tempfile
from typing import Any

from app.security.path_policy import PathPolicy
from app.tools.models import ToolResult

DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_OUTPUT_LIMIT = 8_000
ALLOWED_SUB_AGENT_TOOLS = {"filesystem", "terminal"}
ALLOWED_SUB_AGENT_TOOL_PREFIXES = ("browser_",)
BLOCKED_ENV_KEYS = {
    "DYLD_LIBRARY_PATH",
    "LD_LIBRARY_PATH",
    "PYTHONHOME",
    "PYTHONPATH",
}
NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


class CLIAgentTool:
    """Spawn a specialized sub-agent through a fixed local CLI launcher."""

    def __init__(
        self,
        policy: PathPolicy,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        output_limit: int = DEFAULT_OUTPUT_LIMIT,
    ) -> None:
        self.policy = policy
        self.timeout_seconds = timeout_seconds
        self.output_limit = output_limit

    def spawn_sub_agent(
        self,
        name: str,
        description: str,
        instructions: str,
        tools: list[str],
        timeout_seconds: int | None = None,
    ) -> dict[str, Any]:
        """Spawn a specialized local agent from an agent spec.

        Args:
            name: Stable sub-agent name, such as ``code_reviewer``.
            description: Short summary of the sub-agent's role.
            instructions: The task prompt given to the sub-agent.
            tools: Logical tool names to enable for the sub-agent.
            timeout_seconds: Optional timeout override for this invocation.

        Returns:
            A dictionary with ``status`` and, on success, the launcher output and metadata.
        """

        try:
            return self._spawn_sub_agent(
                name=name,
                description=description,
                instructions=instructions,
                tools=tools,
                timeout_seconds=timeout_seconds,
            ).model_dump()
        except Exception as exc:  # noqa: BLE001
            return ToolResult(status="error", error=str(exc)).model_dump()

    def _spawn_sub_agent(
        self,
        *,
        name: str,
        description: str,
        instructions: str,
        tools: list[str],
        timeout_seconds: int | None,
    ) -> ToolResult:
        self._validate_spec(name, description, instructions, tools)
        spec = {
            "name": name.strip(),
            "description": description.strip(),
            "instructions": instructions.strip(),
            "tools": [tool.strip().lower() for tool in tools],
        }

        timeout = timeout_seconds if timeout_seconds and timeout_seconds > 0 else self.timeout_seconds
        launcher_path = self._launcher_module_path()
        resolved_cwd = self._default_cwd()

        with tempfile.TemporaryDirectory(prefix=f"{spec['name']}-sub-agent-") as temp_dir:
            spec_path = Path(temp_dir) / "sub_agent_spec.json"
            spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
            command = [
                sys.executable,
                "-m",
                "app.agent.sub_agent_launcher",
                "--spec-file",
                str(spec_path),
            ]
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                cwd=resolved_cwd,
                env=self._merge_environment(),
                timeout=timeout,
                preexec_fn=self._resource_limit_hook(timeout),
            )

        return ToolResult(
            status="success" if completed.returncode == 0 else "error",
            data={
                "name": spec["name"],
                "description": spec["description"],
                "instructions": spec["instructions"],
                "tools": spec["tools"],
                "cwd": str(resolved_cwd),
                "command": command,
                "launcher": str(launcher_path),
                "return_code": completed.returncode,
                "stdout": self._truncate(completed.stdout),
                "stderr": self._truncate(completed.stderr),
            },
            error=None if completed.returncode == 0 else self._error_message(completed),
        )

    def _validate_spec(
        self,
        name: str,
        description: str,
        instructions: str,
        tools: Sequence[str],
    ) -> None:
        if not name.strip():
            raise ValueError("name cannot be empty.")
        if not NAME_PATTERN.match(name.strip()):
            raise ValueError("name may only contain letters, numbers, underscores, and hyphens.")
        if not description.strip():
            raise ValueError("description cannot be empty.")
        if not instructions.strip():
            raise ValueError("instructions cannot be empty.")
        if not tools:
            raise ValueError("tools must contain at least one entry.")

        normalized_tools = [tool.strip().lower() for tool in tools]
        if any(not tool for tool in normalized_tools):
            raise ValueError("tools cannot contain empty values.")
        invalid = sorted(
            tool
            for tool in set(normalized_tools)
            if not self._is_allowed_tool_name(tool)
        )
        if invalid:
            raise ValueError(f"Unsupported sub-agent tools: {', '.join(invalid)}.")

    def _is_allowed_tool_name(self, tool_name: str) -> bool:
        if tool_name in ALLOWED_SUB_AGENT_TOOLS:
            return True
        return any(tool_name.startswith(prefix) for prefix in ALLOWED_SUB_AGENT_TOOL_PREFIXES)

    def _merge_environment(self) -> dict[str, str]:
        env = os.environ.copy()
        for key in BLOCKED_ENV_KEYS:
            env.pop(key, None)
        env.setdefault("PYTHONUNBUFFERED", "1")
        if "PATH" not in env:
            env["PATH"] = os.defpath
        backend_root = str(self._backend_root())
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{backend_root}{os.pathsep}{existing_pythonpath}"
            if existing_pythonpath
            else backend_root
        )
        return env

    def _resource_limit_hook(self, timeout_seconds: int) -> Callable[[], None]:
        def _hook() -> None:
            self._apply_resource_limits(timeout_seconds)

        return _hook

    def _apply_resource_limits(self, timeout_seconds: int) -> None:
        try:
            import resource
        except ImportError:  # pragma: no cover - platform dependent
            return

        try:
            resource.setrlimit(resource.RLIMIT_CPU, (timeout_seconds, timeout_seconds))
        except (ValueError, OSError):  # pragma: no cover - platform dependent
            pass

        memory_limit_bytes = 1_000_000_000
        try:
            resource.setrlimit(
                resource.RLIMIT_AS,
                (memory_limit_bytes, memory_limit_bytes),
            )
        except (ValueError, OSError):  # pragma: no cover - platform dependent
            pass

    def _default_cwd(self) -> Path:
        if self.policy.allowed_roots:
            candidate = self.policy.allowed_roots[0]
            if candidate != Path("/"):
                return candidate
        return self._workspace_root()

    def _launcher_module_path(self) -> Path:
        return Path(__file__).resolve().parent.parent / "sub_agent_launcher.py"

    def _backend_root(self) -> Path:
        return Path(__file__).resolve().parents[3]

    def _workspace_root(self) -> Path:
        return Path(__file__).resolve().parents[5]

    def _truncate(self, value: str) -> str:
        if len(value) <= self.output_limit:
            return value
        return f"{value[: self.output_limit]}\n...[truncated]"

    def _error_message(self, completed: subprocess.CompletedProcess[str]) -> str:
        stderr = completed.stderr.strip()
        if stderr:
            return stderr
        return f"Sub-agent exited with code {completed.returncode}."


def build_cli_agent_tools(policy: PathPolicy) -> list[Callable[..., dict[str, Any]]]:
    """Return the CLI sub-agent tool exposed to the root agent."""

    cli_tool = CLIAgentTool(policy)
    return [cli_tool.spawn_sub_agent]
