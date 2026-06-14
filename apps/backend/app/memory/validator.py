from app.memory.schemas import MemoryNodeFrontmatter, NodeStatus, PatchOperation


class MemoryValidationError(ValueError):
    """Raised when a dreamer patch would corrupt durable memory."""


class MemoryValidator:
    """Deterministic checks for NBAM patch operations."""

    def __init__(self, active_node_cap: int = 300) -> None:
        self.active_node_cap = active_node_cap

    def validate_frontmatter(
        self,
        frontmatter: MemoryNodeFrontmatter,
        existing_ids: set[str],
        active_node_count: int,
    ) -> None:
        if frontmatter.id in existing_ids:
            raise MemoryValidationError(f"Duplicate node id: {frontmatter.id}")
        if frontmatter.status == NodeStatus.ACTIVE and active_node_count >= self.active_node_cap:
            raise MemoryValidationError("Active memory node cap would be exceeded.")
        if not frontmatter.tree.strip():
            raise MemoryValidationError("Memory node tree must not be empty.")
        if frontmatter.parent_id == frontmatter.id:
            raise MemoryValidationError("Memory node cannot parent itself.")
        if frontmatter.parent_id and frontmatter.parent_id not in existing_ids:
            raise MemoryValidationError(f"Unknown parent node: {frontmatter.parent_id}")

        for link in frontmatter.links:
            if link.target_id == frontmatter.id:
                raise MemoryValidationError("Self-links are not allowed in MVP.")
            if link.target_id not in existing_ids:
                raise MemoryValidationError(f"Unknown link target: {link.target_id}")

    def validate_patch(self, operation: PatchOperation) -> None:
        allowed = {
            "create_node",
            "update_node_body",
            "update_node_frontmatter",
            "replace_links",
            "deprecate_node",
            "merge_nodes",
            "discard_observation",
        }
        if operation.op not in allowed:
            raise MemoryValidationError(f"Unsupported patch operation: {operation.op}")
