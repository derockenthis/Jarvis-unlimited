from dataclasses import dataclass
import shlex


SHELL_CONTROL_CHARS = set(";&|><`$(){}[]\n\r")
ALLOWED_EXECUTABLES = {
    "cat",
    "cd",
    "find",
    "git",
    "grep",
    "head",
    "ls",
    "node",
    "npm",
    "pwd",
    "pytest",
    "python",
    "python3",
    "rg",
    "tail",
    "uv",
}
READ_ONLY_GIT_SUBCOMMANDS = {"branch", "diff", "log", "show", "status"}


@dataclass(frozen=True)
class ParsedCommand:
    executable: str
    args: list[str]

    @property
    def argv(self) -> list[str]:
        return [self.executable, *self.args]


class CommandPolicy:
    """Validate terminal commands before any subprocess is spawned."""

    def parse(self, command: str) -> ParsedCommand:
        if not command.strip():
            raise ValueError("Command cannot be empty.")
        if any(char in command for char in SHELL_CONTROL_CHARS):
            raise ValueError("Shell control characters are not allowed in terminal commands.")

        try:
            parts = shlex.split(command)
        except ValueError as exc:
            raise ValueError(f"Invalid command syntax: {exc}") from exc

        if not parts:
            raise ValueError("Command cannot be empty.")

        executable = parts[0]
        args = parts[1:]
        if "/" in executable:
            raise ValueError("Commands must use an executable name, not a path.")
        if executable not in ALLOWED_EXECUTABLES:
            raise ValueError(f"Command '{executable}' is not allowed.")
        if executable == "git":
            self._validate_git(args)
        return ParsedCommand(executable=executable, args=args)

    def _validate_git(self, args: list[str]) -> None:
        if not args:
            raise ValueError("git requires an allowed read-only subcommand.")
        if args[0] not in READ_ONLY_GIT_SUBCOMMANDS:
            raise ValueError("Only read-only git subcommands are allowed.")