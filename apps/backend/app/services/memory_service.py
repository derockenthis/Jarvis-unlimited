import sqlite3

from app.config import Settings
from app.memory.node_store import NodeStore
from app.memory.observations import ObservationLog


class MemoryService:
    """Basic runtime wiring for NBAM storage primitives."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.root = settings.memory_root
        self.node_store = NodeStore(self.root)
        self.observation_log = ObservationLog(settings.sqlite_path)
        self._message_indices: dict[str, int] = {}

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.node_store.initialize()

    async def append_observation(self, session_id: str, text: str) -> None:
        self.initialize()
        message_index = self._message_indices.get(session_id, 0)
        await self.observation_log.append(session_id, message_index, text)
        self._message_indices[session_id] = message_index + 1

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