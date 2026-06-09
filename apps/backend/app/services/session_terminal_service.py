from dataclasses import dataclass, field
from pathlib import Path
import subprocess
import uuid

from app.security.command_policy import CommandPolicy
from app.security.path_policy import PathPolicy

OUTPUT_LIMIT = 8_000
COMMAND_TIMEOUT_SECONDS = 20


@dataclass
class TerminalSession:
    terminal_id: str
    user_id: str
    session_id: str
    cwd: Path
    last_result: dict[str, object] = field(default_factory=dict)


class SessionTerminalService:
    """Persistent terminal sessions with guarded command execution."""

    def __init__(self, command_policy: CommandPolicy | None = None) -> None:
        self.command_policy = command_policy or CommandPolicy()
        self._sessions: dict[str, TerminalSession] = {}

    def spawn(
        self,
        *,
        user_id: str,
        session_id: str,
        cwd: str,
        path_policy: PathPolicy,
    ) -> dict[str, object]:
        try:
            resolved_cwd = path_policy.resolve_allowed(cwd)
            if not resolved_cwd.is_dir():
                return {"status": "error", "error": "Terminal cwd must be a directory."}
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "error": str(exc)}

        terminal = TerminalSession(
            terminal_id=str(uuid.uuid4()),
            user_id=user_id,
            session_id=session_id,
            cwd=resolved_cwd,
        )
        self._sessions[self._key(user_id, session_id, terminal.terminal_id)] = terminal
        return {
            "status": "success",
            "data": {"terminal_id": terminal.terminal_id, "cwd": str(terminal.cwd)},
        }

    def run(
        self,
        *,
        user_id: str,
        session_id: str,
        terminal_id: str,
        command: str,
        path_policy: PathPolicy,
    ) -> dict[str, object]:
        terminal = self._sessions.get(self._key(user_id, session_id, terminal_id))
        if terminal is None:
            return {"status": "error", "error": "Unknown terminal session."}

        try:
            parsed = self.command_policy.parse(command)
            if parsed.executable == "cd":
                return self._change_directory(terminal, parsed.args, path_policy)

            completed = subprocess.run(
                parsed.argv,
                check=False,
                capture_output=True,
                cwd=terminal.cwd,
                text=True,
                timeout=COMMAND_TIMEOUT_SECONDS,
            )
            result = {
                "status": "success" if completed.returncode == 0 else "error",
                "data": {
                    "terminal_id": terminal.terminal_id,
                    "cwd": str(terminal.cwd),
                    "command": command,
                    "return_code": completed.returncode,
                    "stdout": self._truncate(completed.stdout),
                    "stderr": self._truncate(completed.stderr),
                },
            }
            if completed.returncode != 0:
                result["error"] = completed.stderr.strip() or f"Command exited {completed.returncode}."
            terminal.last_result = result
            return result
        except subprocess.TimeoutExpired as exc:
            result = {
                "status": "error",
                "error": f"Command timed out after {COMMAND_TIMEOUT_SECONDS} seconds.",
                "data": {
                    "terminal_id": terminal.terminal_id,
                    "cwd": str(terminal.cwd),
                    "stdout": self._truncate(exc.stdout or ""),
                    "stderr": self._truncate(exc.stderr or ""),
                },
            }
            terminal.last_result = result
            return result
        except Exception as exc:  # noqa: BLE001
            result = {"status": "error", "error": str(exc)}
            terminal.last_result = result
            return result

    def read(self, *, user_id: str, session_id: str, terminal_id: str) -> dict[str, object]:
        terminal = self._sessions.get(self._key(user_id, session_id, terminal_id))
        if terminal is None:
            return {"status": "error", "error": "Unknown terminal session."}
        return {
            "status": "success",
            "data": {
                "terminal_id": terminal.terminal_id,
                "cwd": str(terminal.cwd),
                "last_result": terminal.last_result,
            },
        }

    def close(self, *, user_id: str, session_id: str, terminal_id: str) -> dict[str, object]:
        removed = self._sessions.pop(self._key(user_id, session_id, terminal_id), None)
        if removed is None:
            return {"status": "error", "error": "Unknown terminal session."}
        return {"status": "success", "data": {"terminal_id": terminal_id}}

    def _change_directory(
        self, terminal: TerminalSession, args: list[str], path_policy: PathPolicy
    ) -> dict[str, object]:
        if len(args) != 1:
            return {"status": "error", "error": "cd requires exactly one path argument."}
        target = Path(args[0]).expanduser()
        if not target.is_absolute():
            target = terminal.cwd / target
        try:
            resolved = path_policy.resolve_allowed(str(target))
            if not resolved.is_dir():
                return {"status": "error", "error": "cd target must be a directory."}
            terminal.cwd = resolved
            result = {
                "status": "success",
                "data": {"terminal_id": terminal.terminal_id, "cwd": str(terminal.cwd)},
            }
            terminal.last_result = result
            return result
        except Exception as exc:  # noqa: BLE001
            result = {"status": "error", "error": str(exc)}
            terminal.last_result = result
            return result

    def _key(self, user_id: str, session_id: str, terminal_id: str) -> str:
        return f"{user_id}:{session_id}:{terminal_id}"

    def _truncate(self, value: str) -> str:
        if len(value) <= OUTPUT_LIMIT:
            return value
        return f"{value[:OUTPUT_LIMIT]}\n...[truncated]"