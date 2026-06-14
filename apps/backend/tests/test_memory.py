import sqlite3
from datetime import UTC, datetime

import pytest

from app.config import Settings
from app.memory.dreamer import AdkDreamer, DreamerStub
from app.memory.node_document import parse_node_document
from app.memory.schemas import MemoryLink, MemoryNodeFrontmatter, NodeType, Observation, PatchOperation
from app.memory.validator import MemoryValidationError, MemoryValidator
from app.services.conversation_context_service import ConversationContextService
from app.services.memory_service import MemoryService


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


def test_dreamer_stub_links_related_nodes_by_tree() -> None:
    dreamer = DreamerStub()
    observations = [
        Observation(
            id="obs_scope1234",
            timestamp=datetime.now(UTC),
            session_id="session-1",
            message_index=0,
            observation="assistant[local-user]: project scope: ecommerce product pages and event landing pages",
        ),
        Observation(
            id="obs_rule5678",
            timestamp=datetime.now(UTC),
            session_id="session-1",
            message_index=1,
            observation="assistant[local-user]: rule: keep the sidebar compact and explicit",
        ),
    ]

    patches = dreamer.propose(observations)

    assert [patch.op for patch in patches] == ["create_node", "create_node"]
    scope_frontmatter = patches[0].payload["frontmatter"]
    rule_frontmatter = patches[1].payload["frontmatter"]
    assert scope_frontmatter["tree"] == "project_scope"
    assert scope_frontmatter["links"] == []
    assert rule_frontmatter["tree"] == "general"
    assert rule_frontmatter["links"][0]["target_id"] == scope_frontmatter["id"]
    assert rule_frontmatter["links"][0]["relationship"] == "scoped_by"


def test_dreamer_stub_creates_project_scope_node() -> None:
    dreamer = DreamerStub()
    observation = Observation(
        id="obs_scope1234",
        timestamp=datetime.now(UTC),
        session_id="session-1",
        message_index=0,
        observation="assistant[local-user]: project scope: focus on ecommerce product pages and event landing pages",
    )

    patches = dreamer.propose([observation])

    assert len(patches) == 1
    assert patches[0].op == "create_node"
    assert patches[0].payload["frontmatter"]["type"] == "scope"
    assert patches[0].payload["frontmatter"]["tree"] == "project_scope"
    assert patches[0].payload["frontmatter"]["weight"] == 0.9


@pytest.mark.asyncio
async def test_adk_dreamer_parses_json_and_fills_missing_discards(monkeypatch) -> None:
    settings = Settings()
    dreamer = AdkDreamer(settings, fallback=DreamerStub())
    observations = [
        Observation(
            id="obs_rule1234",
            timestamp=datetime.now(UTC),
            session_id="session-1",
            message_index=0,
            observation="assistant[local-user]: rule: prefer compact browser bundles for ollama",
        ),
        Observation(
            id="obs_plain5678",
            timestamp=datetime.now(UTC),
            session_id="session-1",
            message_index=1,
            observation="assistant[local-user]: hello there",
        ),
    ]

    async def _fake_run(_: str) -> str:
        return """
```json
[
  {
    "op": "create_node",
    "node_id": "memory-rule-node",
    "payload": {
      "frontmatter": {
        "id": "memory-rule-node",
        "title": "Compact Browser Bundles",
        "type": "rule",
        "status": "active",
        "created_at": "2026-06-09T00:00:00+00:00",
        "updated_at": "2026-06-09T00:00:00+00:00",
        "valid_from": "2026-06-09T00:00:00+00:00",
        "valid_until": null,
        "confidence": "medium",
        "weight": 0.8,
        "tree": "general",
        "parent_id": null,
        "tags": ["rule"],
        "aliases": [],
        "links": [],
        "source_observations": ["obs_rule1234"]
      },
      "body": "prefer compact browser bundles for ollama",
      "observation_ids": ["obs_rule1234"]
    }
  }
]
```
"""

    monkeypatch.setattr(dreamer, "_run_adk", _fake_run)

    patches = await dreamer.propose(observations)

    assert [patch.op for patch in patches] == ["create_node", "discard_observation"]
    assert patches[0].node_id == "memory-rule-node"
    assert patches[1].payload["observation_id"] == "obs_plain5678"


@pytest.mark.asyncio
async def test_adk_dreamer_falls_back_to_stub_on_invalid_json(monkeypatch) -> None:
    settings = Settings()
    dreamer = AdkDreamer(settings, fallback=DreamerStub())
    observation = Observation(
        id="obs_rule1234",
        timestamp=datetime.now(UTC),
        session_id="session-1",
        message_index=0,
        observation="assistant[local-user]: rule: prefer compact browser bundles for ollama",
    )

    async def _fake_run(_: str) -> str:
        return "not json"

    monkeypatch.setattr(dreamer, "_run_adk", _fake_run)

    patches = await dreamer.propose([observation])

    assert len(patches) == 1
    assert patches[0].op == "create_node"
    assert patches[0].payload["body"] == "prefer compact browser bundles for ollama"


@pytest.mark.asyncio
async def test_conversation_context_service_caches_compacted_session_context(tmp_path) -> None:
    settings = Settings(
        JARVIS_SQLITE_PATH=str(tmp_path / "jarvis.sqlite"),
        JARVIS_MEMORY_ROOT=str(tmp_path / "memory"),
    )
    memory_service = MemoryService(settings)
    context_service = ConversationContextService(settings.sqlite_path)

    await memory_service.append_observation("session-1", "user[local-user]: hello")
    await memory_service.append_observation("session-1", "assistant[local-user]: hi")
    await memory_service.append_observation("session-1", "user[local-user]: summarize this")

    rendered = context_service.render_session_context("session-1", recent_turns=2)
    rendered_again = context_service.render_session_context("session-1", recent_turns=2)

    with sqlite3.connect(settings.sqlite_path) as database:
        cache_rows = database.execute(
            "SELECT COUNT(*) FROM conversation_context_cache WHERE session_id = ?",
            ("session-1",),
        ).fetchone()

    assert "Session context cache:" in rendered
    assert "Recent turns:" in rendered
    assert "user[local-user]" in rendered
    assert rendered == rendered_again
    assert int(cache_rows[0]) == 1


def _create_events_table(database: sqlite3.Connection) -> None:
    database.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            app_name TEXT,
            user_id TEXT,
            session_id TEXT,
            invocation_id TEXT,
            timestamp REAL,
            event_data TEXT
        )
        """
    )


def _insert_session_events(database: sqlite3.Connection, session_id: str, count: int) -> None:
    rows = [
        (
            f"evt-{index}",
            "jarvis-desktop",
            "local-user",
            session_id,
            f"invocation-{index // 2}",
            float(index),
            "{}",
        )
        for index in range(count)
    ]
    database.executemany(
        """
        INSERT INTO events (id, app_name, user_id, session_id, invocation_id, timestamp, event_data)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def test_memory_service_triggers_after_five_new_session_events(tmp_path) -> None:
    settings = Settings(
        JARVIS_SQLITE_PATH=str(tmp_path / "jarvis.sqlite"),
        JARVIS_MEMORY_ROOT=str(tmp_path / "memory"),
        JARVIS_MEMORY_PROMOTION_INTERVAL=5,
    )
    service = MemoryService(settings)
    service.initialize()

    with sqlite3.connect(settings.sqlite_path) as database:
        _create_events_table(database)
        _insert_session_events(database, "session-1", 11)
        database.execute(
            """
            INSERT INTO memory_promotion_state (
                session_id, last_promotion_invocation_count, last_promotion_event_count, updated_at
            ) VALUES (?, ?, ?, ?)
            """,
            ("session-1", 0, 6, "2026-06-10T00:00:00+00:00"),
        )
        database.commit()

    event_count = service.session_event_count("session-1")

    assert event_count == 11
    assert service.event_delta_since_last_promotion("session-1", event_count) == 5
    assert service.should_run_promotion_for_event_count("session-1", event_count) is True


@pytest.mark.asyncio
async def test_memory_service_promotes_unconsolidated_observations_and_creates_tree_root(tmp_path) -> None:
    settings = Settings(
        JARVIS_SQLITE_PATH=str(tmp_path / "jarvis.sqlite"),
        JARVIS_MEMORY_ROOT=str(tmp_path / "memory"),
        JARVIS_MEMORY_PROMOTION_INTERVAL=5,
    )
    service = MemoryService(settings)
    service.dreamer = DreamerStub()

    with sqlite3.connect(settings.sqlite_path) as database:
        _create_events_table(database)
        _insert_session_events(database, "session-1", 5)
        database.commit()

    await service.append_observation(
        "session-1",
        "assistant[local-user]: rule: prefer compact browser bundles for ollama",
    )
    await service.append_observation("session-1", "assistant[local-user]: hello there")

    event_count = service.session_event_count("session-1")
    assert service.should_run_promotion_for_event_count("session-1", event_count) is True

    result = await service.promote_session_observations("session-1", event_count=event_count)
    second_result = await service.promote_session_observations(
        "session-1", event_count=event_count
    )

    assert result["status"] == "success"
    assert result["data"]["consolidated"] == 2
    assert result["data"]["promoted_node_ids"][0] == "general-root"
    assert len(result["data"]["promoted_node_ids"]) == 2
    assert second_result["data"]["consolidated"] == 0
    assert second_result["data"]["promoted_node_ids"] == []
    assert service.should_run_promotion_for_event_count("session-1", event_count) is False

    node_id = next(
        node_id for node_id in result["data"]["promoted_node_ids"] if node_id != "general-root"
    )
    node_content = service.read_node(node_id)
    parsed_node = parse_node_document(node_content["data"]["content"])
    root_content = service.read_node("general-root")
    parsed_root = parse_node_document(root_content["data"]["content"])

    assert node_content["status"] == "success"
    assert parsed_node.frontmatter.parent_id == "general-root"
    assert parsed_node.frontmatter.weight == 0.8
    assert parsed_node.frontmatter.tree == "general"
    assert parsed_node.frontmatter.links == []
    assert parsed_root.frontmatter.parent_id is None
    assert parsed_root.frontmatter.tags == ["entity", "general", "tree_root"]

    with sqlite3.connect(settings.sqlite_path) as database:
        rows = database.execute(
            "SELECT consolidated FROM observations WHERE session_id = ? ORDER BY message_index ASC",
            ("session-1",),
        ).fetchall()

    assert rows == [(1,), (1,)]


def test_memory_service_migrates_legacy_promotion_state_table(tmp_path) -> None:
    sqlite_path = tmp_path / "jarvis.sqlite"
    settings = Settings(
        JARVIS_SQLITE_PATH=str(sqlite_path),
        JARVIS_MEMORY_ROOT=str(tmp_path / "memory"),
    )

    with sqlite3.connect(sqlite_path) as database:
        database.execute(
            """
            CREATE TABLE memory_promotion_state (
                session_id TEXT PRIMARY KEY,
                last_compaction_end_timestamp REAL NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        database.execute(
            """
            INSERT INTO memory_promotion_state (
                session_id,
                last_compaction_end_timestamp,
                updated_at
            )
            VALUES (?, ?, ?)
            """,
            ("legacy-session", 12.5, "2026-06-09T00:00:00+00:00"),
        )
        database.commit()

    service = MemoryService(settings)
    service.initialize()

    with sqlite3.connect(sqlite_path) as database:
        columns = {
            str(row[1]): row
            for row in database.execute("PRAGMA table_info(memory_promotion_state)").fetchall()
        }
        row = database.execute(
            """
            SELECT session_id, last_promotion_invocation_count, last_promotion_event_count, updated_at
            FROM memory_promotion_state
            WHERE session_id = ?
            """,
            ("legacy-session",),
        ).fetchone()

    assert "last_compaction_end_timestamp" not in columns
    assert "last_promotion_invocation_count" in columns
    assert "last_promotion_event_count" in columns
    assert row == ("legacy-session", 0, 0, "2026-06-09T00:00:00+00:00")
