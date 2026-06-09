from datetime import UTC, datetime

import pytest

from app.memory.schemas import MemoryLink, MemoryNodeFrontmatter, NodeType, PatchOperation
from app.memory.validator import MemoryValidationError, MemoryValidator


def test_memory_validator_accepts_supported_patch() -> None:
    validator = MemoryValidator()

    validator.validate_patch(PatchOperation(op="discard_observation"))


def test_memory_validator_rejects_duplicate_node_id() -> None:
    validator = MemoryValidator()
    now = datetime.now(UTC)
    frontmatter = MemoryNodeFrontmatter(
        id="node_existing",
        title="Existing",
        type=NodeType.RULE,
        created_at=now,
        updated_at=now,
        valid_from=now,
    )

    with pytest.raises(MemoryValidationError):
        validator.validate_frontmatter(frontmatter, {"node_existing"}, 0)


def test_memory_validator_rejects_unknown_link_target() -> None:
    validator = MemoryValidator()
    now = datetime.now(UTC)
    frontmatter = MemoryNodeFrontmatter(
        id="node_new",
        title="New",
        type=NodeType.ENTITY,
        created_at=now,
        updated_at=now,
        valid_from=now,
        links=[MemoryLink(target_id="node_missing", relationship="references")],
    )

    with pytest.raises(MemoryValidationError):
        validator.validate_frontmatter(frontmatter, set(), 0)
