import inspect
import sqlite3
from datetime import UTC, datetime

from app.config import Settings
from app.memory.dreamer import AdkDreamer
from app.memory.node_document import parse_node_document, render_node_document
from app.memory.node_store import NodeStore
from app.memory.observations import ObservationLog
from app.memory.schemas import MemoryNodeFrontmatter, NodeStatus, NodeType, PatchOperation
from app.memory.validator import MemoryValidationError, MemoryValidator


CREATE_MEMORY_PROMOTION_STATE_TABLE = """
CREATE TABLE IF NOT EXISTS memory_promotion_state (
    session_id TEXT PRIMARY KEY,
    last_promotion_invocation_count INTEGER NOT NULL,
    last_promotion_event_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
)
"""

CREATE_MEMORY_PROMOTION_STATE_TABLE_MIGRATED = """
CREATE TABLE memory_promotion_state_migrated (
    session_id TEXT PRIMARY KEY,
    last_promotion_invocation_count INTEGER NOT NULL,
    last_promotion_event_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
)
"""


class MemoryService:
    """Basic runtime wiring for NBAM storage primitives."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.root = settings.memory_root
        self.node_store = NodeStore(self.root)
        self.observation_log = ObservationLog(settings.sqlite_path)
        self.validator = MemoryValidator()
        self.dreamer = AdkDreamer(settings)
        self._message_indices: dict[str, int] = {}

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.node_store.initialize()
        with sqlite3.connect(self.observation_log.sqlite_path) as database:
            database.execute(CREATE_MEMORY_PROMOTION_STATE_TABLE)
            table_info = database.execute("PRAGMA table_info(memory_promotion_state)").fetchall()
            column_names = {str(row[1]) for row in table_info}
            event_count_column_added = False
            if "last_promotion_invocation_count" not in column_names:
                database.execute(
                    "ALTER TABLE memory_promotion_state ADD COLUMN last_promotion_invocation_count INTEGER NOT NULL DEFAULT 0"
                )
            if "last_promotion_event_count" not in column_names:
                database.execute(
                    "ALTER TABLE memory_promotion_state ADD COLUMN last_promotion_event_count INTEGER NOT NULL DEFAULT 0"
                )
                event_count_column_added = True
            if "last_compaction_end_timestamp" in column_names:
                self._migrate_memory_promotion_state_table(database)
            elif event_count_column_added:
                self._backfill_promotion_event_counts(database)
            database.commit()

    def _migrate_memory_promotion_state_table(self, database: sqlite3.Connection) -> None:
        database.execute("DROP TABLE IF EXISTS memory_promotion_state_migrated")
        database.execute(CREATE_MEMORY_PROMOTION_STATE_TABLE_MIGRATED)
        database.execute(
            """
            INSERT INTO memory_promotion_state_migrated (
                session_id,
                last_promotion_invocation_count,
                last_promotion_event_count,
                updated_at
            )
            SELECT
                session_id,
                COALESCE(last_promotion_invocation_count, 0),
                0,
                updated_at
            FROM memory_promotion_state
            """
        )
        database.execute("DROP TABLE memory_promotion_state")
        database.execute(
            "ALTER TABLE memory_promotion_state_migrated RENAME TO memory_promotion_state"
        )
        self._backfill_promotion_event_counts(database)

    def _backfill_promotion_event_counts(self, database: sqlite3.Connection) -> None:
        tables = {
            str(row[0])
            for row in database.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        if "events" not in tables:
            return

        database.execute(
            """
            UPDATE memory_promotion_state
            SET last_promotion_event_count = (
                SELECT COUNT(*)
                FROM events
                WHERE events.session_id = memory_promotion_state.session_id
            )
            """
        )

    async def append_observation(self, session_id: str, text: str) -> None:
        self.initialize()
        message_index = self._message_indices.get(session_id, 0)
        await self.observation_log.append(session_id, message_index, text)
        self._message_indices[session_id] = message_index + 1

    async def promote_session_observations(
        self, session_id: str, event_count: int | None = None
    ) -> dict[str, object]:
        self.initialize()
        observations = await self.observation_log.list_unconsolidated_observations_async(session_id)
        if not observations:
            if event_count is not None:
                self._record_promotion_event_count(session_id, event_count)
            return {
                "status": "success",
                "data": {
                    "session_id": session_id,
                    "promoted_node_ids": [],
                    "rejected": [],
                    "consolidated": 0,
                },
            }

        operations = await self._propose_patches(observations)
        existing_ids = set(self.node_store.list_node_ids())
        active_node_count = self._active_node_count(existing_ids)
        promoted_node_ids: list[str] = []
        rejected: list[dict[str, str]] = []
        consolidated_ids: list[str] = []

        for operation in operations:
            observation_ids = self._observation_ids_for_operation(operation)
            try:
                self.validator.validate_patch(operation)
                if operation.op == "discard_observation":
                    consolidated_ids.extend(observation_ids)
                    continue
                if operation.op != "create_node":
                    raise MemoryValidationError(
                        f"Promotion loop does not yet support patch op '{operation.op}'."
                    )

                frontmatter_payload = operation.payload.get("frontmatter")
                if not isinstance(frontmatter_payload, dict):
                    raise MemoryValidationError("Create-node patch is missing frontmatter.")
                frontmatter = MemoryNodeFrontmatter.model_validate(frontmatter_payload)
                body = str(operation.payload.get("body", "")).strip()
                if not body:
                    raise MemoryValidationError("Create-node patch is missing a node body.")

                frontmatter, parent_node_ids, active_node_count = self._ensure_tree_parent_node(
                    frontmatter,
                    existing_ids,
                    active_node_count,
                )
                promoted_node_ids.extend(parent_node_ids)
                self.validator.validate_frontmatter(frontmatter, existing_ids, active_node_count)
                self.node_store.write_node(frontmatter.id, render_node_document(frontmatter, body))
                existing_ids.add(frontmatter.id)
                if frontmatter.status == NodeStatus.ACTIVE:
                    active_node_count += 1
                promoted_node_ids.append(frontmatter.id)
                consolidated_ids.extend(observation_ids or frontmatter.source_observations)
            except (MemoryValidationError, TypeError, ValueError) as exc:
                rejected.append(
                    {
                        "op": operation.op,
                        "node_id": operation.node_id or "",
                        "error": str(exc),
                    }
                )

        consolidated = 0
        if consolidated_ids:
            consolidated = await self.observation_log.mark_consolidated(sorted(set(consolidated_ids)))
        if event_count is not None:
            self._record_promotion_event_count(session_id, event_count)

        return {
            "status": "success",
            "data": {
                "session_id": session_id,
                "promoted_node_ids": promoted_node_ids,
                "rejected": rejected,
                "consolidated": consolidated,
            },
        }

    def status(self) -> dict[str, object]:
        self.initialize()
        observation_count = 0
        sqlite_path = self.observation_log.sqlite_path
        if sqlite_path.exists():
            with sqlite3.connect(sqlite_path) as database:
                row = database.execute("SELECT COUNT(*) FROM observations").fetchone()
                observation_count = int(row[0]) if row else 0
        return {
            "status": "success",
            "data": {
                "memory_root": str(self.root),
                "node_count": len(self.node_store.list_node_ids()),
                "node_ids": self.node_store.list_node_ids(),
                "observation_count": observation_count,
                "observation_log": str(sqlite_path),
                "dreamer_model": self.settings.memory_dreamer_model,
            },
        }

    def read_node(self, node_id: str) -> dict[str, object]:
        try:
            return {
                "status": "success",
                "data": {"node_id": node_id, "content": self.node_store.read_node(node_id)},
            }
        except FileNotFoundError:
            return {"status": "error", "error": f"Memory node '{node_id}' was not found."}

    def session_event_count(self, session_id: str) -> int:
        self.initialize()
        with sqlite3.connect(self.observation_log.sqlite_path) as database:
            tables = {
                str(row[0])
                for row in database.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            if "events" not in tables:
                return 0
            row = database.execute(
                "SELECT COUNT(*) FROM events WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return int(row[0]) if row else 0

    def event_delta_since_last_promotion(self, session_id: str, event_count: int | None) -> int:
        self.initialize()
        if event_count is None:
            return 0

        with sqlite3.connect(self.observation_log.sqlite_path) as database:
            row = database.execute(
                """
                SELECT last_promotion_event_count
                FROM memory_promotion_state
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
        last_event_count = int(row[0]) if row else 0
        return max(0, int(event_count) - last_event_count)

    def should_run_promotion_for_event_count(
        self, session_id: str, event_count: int | None
    ) -> bool:
        self.initialize()
        if event_count is None:
            return False

        interval = max(1, self.settings.memory_promotion_interval)
        if int(event_count) <= 0:
            return False

        return self.event_delta_since_last_promotion(session_id, event_count) >= interval

    def _observation_ids_for_operation(self, operation: PatchOperation) -> list[str]:
        explicit_ids = operation.payload.get("observation_ids")
        if isinstance(explicit_ids, list):
            return [str(item) for item in explicit_ids if str(item).strip()]

        observation_id = operation.payload.get("observation_id")
        if observation_id is not None:
            return [str(observation_id)]
        return []

    def _active_node_count(self, node_ids: set[str]) -> int:
        active_count = 0
        for node_id in node_ids:
            try:
                document = parse_node_document(self.node_store.read_node(node_id))
            except Exception:
                active_count += 1
                continue
            if document.frontmatter.status == NodeStatus.ACTIVE:
                active_count += 1
        return active_count

    async def _propose_patches(self, observations: list[object]) -> list[PatchOperation]:
        result = self.dreamer.propose(observations)
        if inspect.isawaitable(result):
            result = await result
        return list(result)

    def _record_promotion_event_count(self, session_id: str, event_count: int) -> None:
        with sqlite3.connect(self.observation_log.sqlite_path) as database:
            database.execute(
                """
                INSERT INTO memory_promotion_state (
                    session_id, last_promotion_invocation_count, last_promotion_event_count, updated_at
                )
                VALUES (?, 0, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    last_promotion_event_count = excluded.last_promotion_event_count,
                    updated_at = excluded.updated_at
                """,
                (session_id, int(event_count), datetime.now(UTC).isoformat()),
            )
            database.commit()

    def _ensure_tree_parent_node(
        self,
        frontmatter: MemoryNodeFrontmatter,
        existing_ids: set[str],
        active_node_count: int,
    ) -> tuple[MemoryNodeFrontmatter, list[str], int]:
        if frontmatter.parent_id:
            return frontmatter, [], active_node_count

        root_id = self._tree_root_id(frontmatter.tree)
        if frontmatter.id == root_id:
            return frontmatter, [], active_node_count

        created_parent_ids: list[str] = []
        if root_id not in existing_ids:
            parent_frontmatter = self._build_tree_root_frontmatter(frontmatter, root_id)
            self.validator.validate_frontmatter(parent_frontmatter, existing_ids, active_node_count)
            self.node_store.write_node(
                parent_frontmatter.id,
                render_node_document(
                    parent_frontmatter,
                    self._tree_root_body(frontmatter.tree),
                ),
            )
            existing_ids.add(parent_frontmatter.id)
            created_parent_ids.append(parent_frontmatter.id)
            if parent_frontmatter.status == NodeStatus.ACTIVE:
                active_node_count += 1

        return (
            frontmatter.model_copy(update={"parent_id": root_id}),
            created_parent_ids,
            active_node_count,
        )

    def _tree_root_id(self, tree: str) -> str:
        normalized_tree = (tree or "general").strip().replace("_", "-")
        return f"{normalized_tree}-root"

    def _build_tree_root_frontmatter(
        self, frontmatter: MemoryNodeFrontmatter, root_id: str
    ) -> MemoryNodeFrontmatter:
        tree = frontmatter.tree.strip() or "general"
        is_scope_tree = tree == "project_scope"
        title = "Project Scope" if is_scope_tree else tree.replace("_", " ").title()
        node_type = NodeType.SCOPE if is_scope_tree else NodeType.ENTITY
        return MemoryNodeFrontmatter(
            id=root_id,
            title=title,
            type=node_type,
            status=NodeStatus.ACTIVE,
            created_at=frontmatter.created_at,
            updated_at=frontmatter.updated_at,
            valid_from=frontmatter.valid_from,
            valid_until=None,
            confidence="high",
            weight=1.0 if is_scope_tree else 0.7,
            tree=tree,
            parent_id=None,
            tags=sorted(set(["tree_root", tree, node_type.value])),
            aliases=[],
            links=[],
            source_observations=list(frontmatter.source_observations),
        )

    def _tree_root_body(self, tree: str) -> str:
        label = (tree or "general").strip().replace("_", " ")
        return f"System root node for the {label} memory tree."