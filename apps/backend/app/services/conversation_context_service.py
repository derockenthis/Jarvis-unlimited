from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.agent.provider_config import ProviderRuntimeConfig
from app.config import Settings
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


@dataclass(frozen=True, slots=True)
class CachedContext:
    source_message_index: int
    cached_context: str


@dataclass(frozen=True, slots=True)
class SessionEvent:
    event_id: str
    timestamp: float
    event_data: str


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

        latest_cached_context = self._get_latest_cached_context(session_id)
        if latest_cached_context is not None:
            recent_after_cache = [
                observation
                for observation in observations
                if latest_cached_context.source_message_index
                < observation.message_index
                < current_index
            ][-recent_turns:]
            parts = [latest_cached_context.cached_context]
            if recent_after_cache:
                parts.append("Recent turns after cache:")
                for observation in recent_after_cache:
                    parts.append(f"- {self._format_observation(observation.observation)}")
            return "\n".join(parts).strip()

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

    async def compact_session_context_with_model(
        self,
        session_id: str,
        settings: Settings,
        provider_config: ProviderRuntimeConfig,
        event_limit: int,
        overlap: int,
    ) -> str | None:
        """Summarize recent ADK event rows into the prompt context cache."""

        self.initialize()
        source_message_index = self._latest_message_index(session_id)
        if source_message_index < 0:
            return None

        events = self._list_session_events(session_id, max(1, event_limit))
        if not events:
            return None

        existing_context = self._get_latest_cached_context(session_id)
        event_lines = [
            f"{index}. {self._format_event(event)}"
            for index, event in enumerate(events, start=1)
        ]
        prompt_parts = [
            "Create a compact session context cache for the next assistant turn.",
            "Preserve user goals, decisions, constraints, tool results, unresolved tasks, and important facts.",
            "Remove duplicate logs, low-value debug noise, and transient implementation details.",
            f"The last {max(0, overlap)} raw ADK event row(s) are retained separately as overlap, so focus on durable context.",
        ]
        if existing_context is not None:
            prompt_parts.extend(["Existing compact context:", existing_context.cached_context])
        prompt_parts.extend(["Recent ADK events to review:", "\n".join(event_lines)])

        from litellm import acompletion

        response = await acompletion(
            model=provider_config.litellm_model(settings),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You write concise conversation memory for a local desktop assistant. "
                        "Return only the compact context text."
                    ),
                },
                {"role": "user", "content": "\n\n".join(prompt_parts)},
            ],
            **provider_config.litellm_kwargs(settings),
        )
        compacted_text = self._extract_completion_text(response)
        if not compacted_text:
            return None

        cached_context = "\n".join(
            [
                "Session context cache:",
                "Earlier compacted context:",
                compacted_text,
            ]
        ).strip()
        self._store_cached_context(session_id, source_message_index, cached_context)
        return cached_context

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

    def _get_latest_cached_context(self, session_id: str) -> CachedContext | None:
        with sqlite3.connect(self.sqlite_path) as database:
            row = database.execute(
                """
                SELECT source_message_index, cached_context
                FROM conversation_context_cache
                WHERE session_id = ?
                ORDER BY source_message_index DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return CachedContext(source_message_index=int(row[0]), cached_context=str(row[1]))

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

    def _list_session_events(self, session_id: str, limit: int) -> list[SessionEvent]:
        with sqlite3.connect(self.sqlite_path) as database:
            tables = {
                str(row[0])
                for row in database.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            if "events" not in tables:
                return []
            rows = database.execute(
                """
                SELECT id, timestamp, event_data
                FROM events
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [
            SessionEvent(event_id=str(row[0]), timestamp=float(row[1]), event_data=str(row[2]))
            for row in reversed(rows)
        ]

    def _format_event(self, event: SessionEvent) -> str:
        try:
            parsed = json.loads(event.event_data)
        except json.JSONDecodeError:
            return event.event_data.strip()[:900]
        summary = self._extract_event_summary(parsed)
        return summary[:900] if summary else json.dumps(parsed, ensure_ascii=True)[:900]

    def _extract_event_summary(self, value: object) -> str:
        fragments: list[str] = []

        def walk(node: object, key: str = "") -> None:
            if len(" ".join(fragments)) > 1200:
                return
            if isinstance(node, dict):
                for field in (
                    "author",
                    "role",
                    "name",
                    "finish_reason",
                    "error_message",
                    "text",
                ):
                    item = node.get(field)
                    if isinstance(item, str) and item.strip():
                        fragments.append(f"{field}={item.strip()}")
                for child_key, child_value in node.items():
                    if child_key in {"timestamp", "id", "invocation_id"}:
                        continue
                    walk(child_value, child_key)
            elif isinstance(node, list):
                for item in node:
                    walk(item, key)
            elif isinstance(node, str) and key in {"text", "content", "output"} and node.strip():
                fragments.append(node.strip())

        walk(value)
        deduped = list(dict.fromkeys(fragment[:300] for fragment in fragments if fragment.strip()))
        return " | ".join(deduped)

    def _extract_completion_text(self, response: object) -> str:
        try:
            choices = getattr(response, "choices", None) or response["choices"]  # type: ignore[index]
            if not choices:
                return ""
            message = getattr(choices[0], "message", None) or choices[0]["message"]
            content = getattr(message, "content", None) or message.get("content", "")
            return str(content).strip()
        except (AttributeError, KeyError, IndexError, TypeError):
            return ""
