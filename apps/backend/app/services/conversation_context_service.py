from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.memory.observations import ObservationLog


CREATE_CONTEXT_CACHE_TABLE = """
CREATE TABLE IF NOT EXISTS conversation_context_cache (
  session_id TEXT PRIMARY KEY,
  source_message_index INTEGER NOT NULL,
  cached_context TEXT NOT NULL,
  updated_at TEXT NOT NULL
)
"""


@dataclass(frozen=True, slots=True)
class SessionObservation:
    message_index: int
    observation: str


class ConversationContextService:
    """Builds and caches a compact prompt prefix from session observations."""

    def __init__(self, sqlite_path: Path) -> None:
        self.sqlite_path = sqlite_path
        self.observation_log = ObservationLog(sqlite_path)

    def initialize(self) -> None:
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.sqlite_path) as database:
            database.execute(CREATE_CONTEXT_CACHE_TABLE)
            database.commit()

    def render_session_context(self, session_id: str, recent_turns: int = 6) -> str:
        """Return a cached, compact session context block for prompt injection."""

        self.initialize()
        current_index = self._latest_message_index(session_id)
        if current_index < 0:
            return ""

        cached_context = self._get_cached_context(session_id, current_index)
        if cached_context is not None:
            return cached_context

        observations = self._list_observations(session_id)
        if not observations:
            return ""

        history = observations[:-1]
        if not history:
            return ""

        recent = history[-recent_turns:]
        older = history[:-recent_turns]

        parts = ["Session context cache:"]
        if older:
            parts.append("Earlier context:")
            for observation in older[-12:]:
                parts.append(f"- {self._format_observation(observation.observation)}")
        if recent:
            parts.append("Recent turns:")
            for observation in recent:
                parts.append(f"- {self._format_observation(observation.observation)}")

        rendered_context = "\n".join(parts).strip()
        self._store_cached_context(session_id, current_index, rendered_context)
        return rendered_context

    def _latest_message_index(self, session_id: str) -> int:
        with sqlite3.connect(self.sqlite_path) as database:
            row = database.execute(
                "SELECT COALESCE(MAX(message_index), -1) FROM observations WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            return int(row[0]) if row else -1

    def _list_observations(self, session_id: str) -> list[SessionObservation]:
        with sqlite3.connect(self.sqlite_path) as database:
            rows = database.execute(
                """
                SELECT message_index, observation
                FROM observations
                WHERE session_id = ?
                ORDER BY message_index ASC
                """,
                (session_id,),
            ).fetchall()
        return [SessionObservation(message_index=int(row[0]), observation=str(row[1])) for row in rows]

    def _get_cached_context(self, session_id: str, source_message_index: int) -> str | None:
        with sqlite3.connect(self.sqlite_path) as database:
            row = database.execute(
                """
                SELECT cached_context
                FROM conversation_context_cache
                WHERE session_id = ? AND source_message_index = ?
                """,
                (session_id, source_message_index),
            ).fetchone()
            return str(row[0]) if row else None

    def _store_cached_context(
        self, session_id: str, source_message_index: int, cached_context: str
    ) -> None:
        with sqlite3.connect(self.sqlite_path) as database:
            database.execute(
                """
                INSERT INTO conversation_context_cache (
                    session_id, source_message_index, cached_context, updated_at
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    source_message_index = excluded.source_message_index,
                    cached_context = excluded.cached_context,
                    updated_at = excluded.updated_at
                """,
                (
                    session_id,
                    source_message_index,
                    cached_context,
                    datetime.now(UTC).isoformat(),
                ),
            )
            database.commit()

    def _format_observation(self, observation: str) -> str:
        cleaned = observation.strip()
        if ": " in cleaned:
            role, content = cleaned.split(": ", 1)
            return f"{role}: {content[:220]}" if len(content) > 220 else f"{role}: {content}"
        return cleaned[:240]