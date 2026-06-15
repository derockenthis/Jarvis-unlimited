from collections.abc import AsyncIterator
import sqlite3
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.config import Settings
from app.schemas import ChatEvent, ChatRequest, Conversation, ConversationMessage

if TYPE_CHECKING:
    from app.agent.runner import AgentStreamRunner


class ChatService:
    def __init__(self, runtime: "AgentStreamRunner", settings: Settings) -> None:
        self.runtime = runtime
        self.sqlite_path = settings.sqlite_path

    def initialize(self) -> None:
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.sqlite_path) as database:
            database.execute(CREATE_CONVERSATIONS_TABLE)
            database.execute(CREATE_CONVERSATION_MESSAGES_TABLE)
            database.commit()

    async def save_conversation(self, session_id: str, user_id: str, title: str) -> None:
        self.initialize()
        timestamp = datetime.now(UTC).isoformat()
        with sqlite3.connect(self.sqlite_path) as database:
            database.execute(
                """
                INSERT INTO conversations (id, user_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    user_id=excluded.user_id,
                    updated_at=excluded.updated_at
                """,
                (session_id, user_id, title, timestamp, timestamp),
            )
            database.commit()

    async def save_conversation_message(
        self, conversation_id: str, role: str, content: str
    ) -> None:
        self.initialize()
        with sqlite3.connect(self.sqlite_path) as database:
            database.execute(
                """
                INSERT INTO conversation_messages (conversation_id, role, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (conversation_id, role, content, datetime.now(UTC).isoformat()),
            )
            database.commit()

    async def list_conversations(
        self, user_id: str = "local-user", limit: int = 50
    ) -> list[Conversation]:
        self.initialize()
        with sqlite3.connect(self.sqlite_path) as database:
            database.row_factory = sqlite3.Row
            rows = database.execute(
                """
                SELECT id, user_id, title, created_at, updated_at
                FROM conversations
                WHERE user_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()

        return [Conversation(**dict(row)) for row in rows]

    async def get_conversation(self, conversation_id: str) -> Conversation | None:
        self.initialize()
        with sqlite3.connect(self.sqlite_path) as database:
            database.row_factory = sqlite3.Row
            row = database.execute(
                """
                SELECT id, user_id, title, created_at, updated_at
                FROM conversations
                WHERE id = ?
                """,
                (conversation_id,),
            ).fetchone()

        if row is None:
            return None

        return Conversation(**dict(row))

    async def get_conversation_messages(self, conversation_id: str) -> list[ConversationMessage]:
        self.initialize()
        with sqlite3.connect(self.sqlite_path) as database:
            database.row_factory = sqlite3.Row
            rows = database.execute(
                """
                SELECT id, conversation_id, role, content, created_at
                FROM conversation_messages
                WHERE conversation_id = ?
                ORDER BY id ASC
                """,
                (conversation_id,),
            ).fetchall()

        return [ConversationMessage(**dict(row)) for row in rows]

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[ChatEvent]:
        async for event in self.runtime.stream_chat(request, conversation_store=self):
            yield event


CREATE_CONVERSATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

CREATE_CONVERSATION_MESSAGES_TABLE = """
CREATE TABLE IF NOT EXISTS conversation_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
)
"""
