from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment and optional .env files."""

    model_config = SettingsConfigDict(
        env_file=("../../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    google_ai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_AI_API_KEY", "GOOGLE_API_KEY"),
    )
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(
        default="openai/gpt-4o-mini",
        validation_alias=AliasChoices("AGENT_MODEL_ID", "OPENROUTER_MODEL"),
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        validation_alias=AliasChoices("OPENROUTER_API_BASE", "OPENROUTER_BASE_URL"),
    )
    openrouter_vision_model: str = Field(
        default="openai/gpt-4o-mini",
        validation_alias=AliasChoices("OPENROUTER_VISION_MODEL", "AGENT_VISION_MODEL"),
    )
    openrouter_transcription_model: str = Field(
        default="nvidia/parakeet-tdt-0.6b-v3",
        validation_alias=AliasChoices("OPENROUTER_TRANSCRIPTION_MODEL", "SPEECH_TO_TEXT_MODEL"),
    )
    memory_dreamer_model: str = Field(
        default="google/gemini-3.1-flash-lite",
        validation_alias=AliasChoices("NBAM_DREAMER_MODEL", "MEMORY_DREAMER_MODEL"),
    )
    sqlite_path: Path = Field(default=Path("data/jarvis.sqlite"), alias="JARVIS_SQLITE_PATH")
    memory_root: Path = Field(default=Path("data/memory"), alias="JARVIS_MEMORY_ROOT")
    screenshot_dir: Path = Field(default=Path("data/screenshots"), alias="JARVIS_SCREENSHOT_DIR")
    allowed_roots: str = Field(default="", alias="JARVIS_ALLOWED_ROOTS")
    full_filesystem_access: bool = Field(default=True, alias="JARVIS_FULL_FILESYSTEM_ACCESS")

    @property
    def openrouter_litellm_model(self) -> str:
        if self.openrouter_model.startswith("openrouter/"):
            return self.openrouter_model
        return f"openrouter/{self.openrouter_model}"

    @property
    def openrouter_litellm_vision_model(self) -> str:
        if self.openrouter_vision_model.startswith("openrouter/"):
            return self.openrouter_vision_model
        return f"openrouter/{self.openrouter_vision_model}"

    @property
    def openrouter_transcription_model_slug(self) -> str:
        if self.openrouter_transcription_model.startswith("openrouter/"):
            return self.openrouter_transcription_model.removeprefix("openrouter/")
        return self.openrouter_transcription_model

    @property
    def memory_dreamer_litellm_model(self) -> str:
        if self.memory_dreamer_model.startswith("openrouter/"):
            return self.memory_dreamer_model
        return f"openrouter/{self.memory_dreamer_model}"

    @property
    def allowed_root_paths(self) -> list[Path]:
        if self.full_filesystem_access:
            return [Path("/").resolve()]
        roots = [root.strip() for root in self.allowed_roots.split(":") if root.strip()]
        return [Path(root).expanduser().resolve() for root in roots]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
