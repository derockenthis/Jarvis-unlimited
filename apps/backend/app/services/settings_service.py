from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from app.config import Settings
from app.schemas import ModelSettingsResponse, ProviderModelSettings, UpsertModelSettingsRequest


CREATE_APP_PREFERENCES_TABLE = """
CREATE TABLE IF NOT EXISTS app_preferences (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL
)
"""


CREATE_PROVIDER_MODEL_SETTINGS_TABLE = """
CREATE TABLE IF NOT EXISTS provider_model_settings (
  provider TEXT PRIMARY KEY,
  model TEXT NOT NULL DEFAULT '',
  api_key TEXT NOT NULL DEFAULT '',
  base_url TEXT NOT NULL DEFAULT '',
  speech_model TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL
)
"""


class SettingsService:
    """Persist renderer model/provider settings in the local application SQLite database."""

    def __init__(self, settings: Settings) -> None:
        self.sqlite_path = settings.sqlite_path

    def initialize(self) -> None:
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.sqlite_path) as database:
            database.execute(CREATE_APP_PREFERENCES_TABLE)
            database.execute(CREATE_PROVIDER_MODEL_SETTINGS_TABLE)
            database.commit()

    def get_model_settings(self) -> ModelSettingsResponse:
        self.initialize()
        with sqlite3.connect(self.sqlite_path) as database:
            current_provider_row = database.execute(
                "SELECT value FROM app_preferences WHERE key = ?",
                ("current_provider",),
            ).fetchone()
            provider_rows = database.execute(
                "SELECT provider, model, api_key, base_url, speech_model FROM provider_model_settings ORDER BY provider"
            ).fetchall()

        return ModelSettingsResponse(
            current_provider=(current_provider_row[0] if current_provider_row else "openrouter"),
            providers=[
                ProviderModelSettings(
                    provider=str(row[0]),
                    model=str(row[1] or ""),
                    api_key=str(row[2] or ""),
                    base_url=str(row[3] or ""),
                    speech_model=str(row[4] or ""),
                )
                for row in provider_rows
            ],
        )

    def save_model_settings(self, request: UpsertModelSettingsRequest) -> ModelSettingsResponse:
        self.initialize()
        timestamp = datetime.now(UTC).isoformat()

        with sqlite3.connect(self.sqlite_path) as database:
            database.execute(
                """
                INSERT INTO provider_model_settings (provider, model, api_key, base_url, speech_model, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider) DO UPDATE SET
                  model = excluded.model,
                  api_key = excluded.api_key,
                  base_url = excluded.base_url,
                  speech_model = excluded.speech_model,
                  updated_at = excluded.updated_at
                """,
                (request.provider, request.model, request.api_key, request.base_url, request.speech_model, timestamp),
            )
            database.execute(
                """
                INSERT INTO app_preferences (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                  value = excluded.value,
                  updated_at = excluded.updated_at
                """,
                ("current_provider", request.provider, timestamp),
            )
            database.commit()

        return self.get_model_settings()