from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class NodeType(StrEnum):
    ARCHITECTURAL_DECISION = "architectural_decision"
    ENTITY = "entity"
    RULE = "rule"
    EVENT = "event"
    TASK = "task"
    SCOPE = "scope"


class NodeStatus(StrEnum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class MemoryLink(BaseModel):
    target_id: str
    relationship: str


class MemoryNodeFrontmatter(BaseModel):
    id: str
    title: str
    type: NodeType
    status: NodeStatus = NodeStatus.ACTIVE
    created_at: datetime
    updated_at: datetime
    valid_from: datetime
    valid_until: datetime | None = None
    confidence: Literal["low", "medium", "high"] = "medium"
    weight: float = Field(default=0.5, ge=0.0, le=1.0)
    tree: str = Field(default="general", min_length=1)
    parent_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    links: list[MemoryLink] = Field(default_factory=list)
    source_observations: list[str] = Field(default_factory=list)


class Observation(BaseModel):
    id: str
    timestamp: datetime
    session_id: str
    message_index: int
    observation: str


class PatchOperation(BaseModel):
    op: Literal[
        "create_node",
        "update_node_body",
        "update_node_frontmatter",
        "replace_links",
        "deprecate_node",
        "merge_nodes",
        "discard_observation",
    ]
    node_id: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)
