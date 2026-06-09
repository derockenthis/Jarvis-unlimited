from pathlib import Path


class PathPolicy:
    """Validates that filesystem access stays inside user-granted roots."""

    def __init__(self, allowed_roots: list[Path], full_access: bool = False) -> None:
        self.allowed_roots = [root.expanduser().resolve() for root in allowed_roots]
        self.full_access = full_access

    def resolve_allowed(self, path: str | Path) -> Path:
        candidate = Path(path).expanduser().resolve()
        if self.full_access:
            return candidate

        if not self.allowed_roots:
            raise PermissionError("No workspace roots have been granted.")

        for root in self.allowed_roots:
            if candidate == root or root in candidate.parents:
                return candidate

        raise PermissionError(f"Path is outside granted workspace roots: {candidate}")
