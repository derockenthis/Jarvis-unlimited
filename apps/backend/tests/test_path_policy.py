from pathlib import Path

import pytest

from app.security.path_policy import PathPolicy


def test_path_policy_allows_paths_inside_root(tmp_path: Path) -> None:
    allowed_file = tmp_path / "repo" / "README.md"
    allowed_file.parent.mkdir()
    allowed_file.write_text("hello", encoding="utf-8")

    policy = PathPolicy([tmp_path / "repo"])

    assert policy.resolve_allowed(allowed_file) == allowed_file.resolve()


def test_path_policy_rejects_paths_outside_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    outside = tmp_path / "outside.txt"
    repo.mkdir()
    outside.write_text("nope", encoding="utf-8")

    policy = PathPolicy([repo])

    with pytest.raises(PermissionError):
        policy.resolve_allowed(outside)


def test_path_policy_rejects_when_no_roots(tmp_path: Path) -> None:
    policy = PathPolicy([])

    with pytest.raises(PermissionError):
        policy.resolve_allowed(tmp_path)


def test_path_policy_allows_any_path_with_full_access(tmp_path: Path) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("ok", encoding="utf-8")
    policy = PathPolicy([], full_access=True)

    assert policy.resolve_allowed(outside) == outside.resolve()
