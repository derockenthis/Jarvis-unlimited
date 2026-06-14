from __future__ import annotations

import json
from dataclasses import dataclass

from app.memory.schemas import MemoryNodeFrontmatter


NODE_FRONTMATTER_DELIMITER = "---"


@dataclass(frozen=True, slots=True)
class MemoryNodeDocument:
    frontmatter: MemoryNodeFrontmatter
    body: str


def render_node_document(frontmatter: MemoryNodeFrontmatter, body: str) -> str:
    frontmatter_json = json.dumps(frontmatter.model_dump(mode="json"), indent=2, sort_keys=True)
    normalized_body = body.strip("\n")
    if normalized_body:
        return f"{NODE_FRONTMATTER_DELIMITER}\n{frontmatter_json}\n{NODE_FRONTMATTER_DELIMITER}\n{normalized_body}\n"
    return f"{NODE_FRONTMATTER_DELIMITER}\n{frontmatter_json}\n{NODE_FRONTMATTER_DELIMITER}\n"


def parse_node_document(content: str) -> MemoryNodeDocument:
    lines = content.splitlines()
    if not lines or lines[0].strip() != NODE_FRONTMATTER_DELIMITER:
        raise ValueError("Node document is missing frontmatter start delimiter.")

    try:
        frontmatter_end = lines.index(NODE_FRONTMATTER_DELIMITER, 1)
    except ValueError as exc:
        raise ValueError("Node document is missing frontmatter end delimiter.") from exc

    frontmatter_text = "\n".join(lines[1:frontmatter_end]).strip()
    body = "\n".join(lines[frontmatter_end + 1 :]).lstrip("\n")
    frontmatter = MemoryNodeFrontmatter.model_validate(json.loads(frontmatter_text))
    return MemoryNodeDocument(frontmatter=frontmatter, body=body)