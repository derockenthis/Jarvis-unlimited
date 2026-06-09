from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import aiosqlite

from app.memory.schemas import Observation


CREATE_OBSERVATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS observations (
  offset INTEGER PRIMARY KEY AUTOINCREMENT,
  id TEXT NOT NULL UNIQUE,
  timestamp TEXT NOT NULL,
  session_id TEXT NOT NULL,
  message_index INTEGER NOT NULL,
  observation TEXT NOT NULL,
  consolidated INTEGER NOT NULL DEFAULT 0
)
"""


class ObservationLog:
    """Append-only observation log for live-session memory events."""

    def __init__(self, sqlite_path: Path) -> None:
        self.sqlite_path = sqlite_path

    async def initialize(self) -> None:
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.sqlite_path) as database:
            await database.execute(CREATE_OBSERVATIONS_TABLE)
            await database.commit()

    async def append(self, session_id: str, message_index: int, text: str) -> Observation:
        await self.initialize()
        observation = Observation(
            id=f"obs_{uuid4().hex}",
            timestamp=datetime.now(UTC),
            session_id=session_id,
            message_index=message_index,
            observation=text,
        )
        async with aiosqlite.connect(self.sqlite_path) as database:
            await database.execute(
                """
                INSERT INTO observations (id, timestamp, session_id, message_index, observation)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    observation.id,
                    observation.timestamp.isoformat(),
                    observation.session_id,
                    observation.message_index,
                    observation.observation,
                ),
            )
            await database.commit()
        return observation
