from datetime import UTC, datetime
from pathlib import Path
from collections.abc import Sequence
from uuid import uuid4
import sqlite3

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

    async def list_session_observations_async(self, session_id: str) -> list[Observation]:
        await self.initialize()
        async with aiosqlite.connect(self.sqlite_path) as database:
            cursor = await database.execute(
                """
                SELECT id, timestamp, session_id, message_index, observation
                FROM observations
                WHERE session_id = ?
                ORDER BY message_index ASC
                """,
                (session_id,),
            )
            rows = await cursor.fetchall()
        return [
            Observation(
                id=str(row[0]),
                timestamp=datetime.fromisoformat(str(row[1])),
                session_id=str(row[2]),
                message_index=int(row[3]),
                observation=str(row[4]),
            )
            for row in rows
        ]

    async def list_unconsolidated_observations_async(self, session_id: str) -> list[Observation]:
        await self.initialize()
        async with aiosqlite.connect(self.sqlite_path) as database:
            cursor = await database.execute(
                """
                SELECT id, timestamp, session_id, message_index, observation
                FROM observations
                WHERE session_id = ? AND consolidated = 0
                ORDER BY message_index ASC
                """,
                (session_id,),
            )
            rows = await cursor.fetchall()
        return [
            Observation(
                id=str(row[0]),
                timestamp=datetime.fromisoformat(str(row[1])),
                session_id=str(row[2]),
                message_index=int(row[3]),
                observation=str(row[4]),
            )
            for row in rows
        ]

    async def mark_consolidated(self, observation_ids: Sequence[str]) -> int:
        await self.initialize()
        unique_ids = [observation_id for observation_id in dict.fromkeys(observation_ids) if observation_id]
        if not unique_ids:
            return 0

        placeholders = ", ".join("?" for _ in unique_ids)
        async with aiosqlite.connect(self.sqlite_path) as database:
            cursor = await database.execute(
                f"""
                UPDATE observations
                SET consolidated = 1
                WHERE id IN ({placeholders})
                """,
                unique_ids,
            )
            await database.commit()
            return int(cursor.rowcount or 0)

    def latest_message_index(self, session_id: str) -> int:
        self.initialize()
        with sqlite3.connect(self.sqlite_path) as database:
            row = database.execute(
                "SELECT COALESCE(MAX(message_index), -1) FROM observations WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return int(row[0]) if row else -1
