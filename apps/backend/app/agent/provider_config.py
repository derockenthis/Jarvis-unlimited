from dataclasses import dataclass

from app.config import Settings


@dataclass(frozen=True, slots=True)
class ProviderRuntimeConfig:
    """Request-scoped model provider configuration for ADK runs."""

    provider: str = "openrouter"
    model_name: str | None = None
    api_key: str | None = None
    base_url: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider", (self.provider or "openrouter").strip().lower())
        object.__setattr__(self, "model_name", self.model_name.strip() if self.model_name else None)
        object.__setattr__(self, "api_key", self.api_key.strip() if self.api_key else None)
        object.__setattr__(self, "base_url", self.base_url.strip() if self.base_url else None)

    @property
    def supports_adk_tools(self) -> bool:
        return True

    @property
    def playwright_bundle(self) -> str:
        if self.provider == "ollama":
            return "core"
        if self.provider == "openai":
            return "read"
        return "read"

    @property
    def prefers_compact_browser_tools(self) -> bool:
        return self.provider == "ollama"

    def missing_configuration(self, settings: Settings) -> str | None:
        if self.provider == "openrouter" and not (self.api_key or settings.openrouter_api_key):
            return "OpenRouter is not configured. Enter an OpenRouter API key or set OPENROUTER_API_KEY."
        if self.provider == "openai" and not self.api_key:
            return "OpenAI is not configured. Enter an OpenAI API key in the Models section."
        return None

    def litellm_model(self, settings: Settings) -> str:
        if not self.model_name:
            return settings.openrouter_litellm_model
        if self.provider == "openrouter":
            return (
                self.model_name
                if self.model_name.startswith("openrouter/")
                else f"openrouter/{self.model_name}"
            )
        if self.provider == "ollama":
            return (
                self.model_name
                if self.model_name.startswith(("ollama/", "ollama_chat/"))
                else f"ollama_chat/{self.model_name}"
            )
        if self.provider == "openai":
            return (
                self.model_name
                if self.model_name.startswith("openai/")
                else f"openai/{self.model_name}"
            )
        return self.model_name

    def litellm_kwargs(self, settings: Settings) -> dict[str, str]:
        kwargs: dict[str, str] = {}
        if self.provider == "openrouter":
            kwargs["api_key"] = self.api_key or settings.openrouter_api_key
            kwargs["api_base"] = self.base_url or settings.openrouter_base_url
        elif self.provider == "openai":
            kwargs["api_key"] = self.api_key or ""
            if self.base_url:
                kwargs["api_base"] = self.base_url
        elif self.provider == "ollama":
            kwargs["api_base"] = self.base_url or "http://localhost:11434"
            kwargs["custom_llm_provider"] = "ollama_chat"
        return kwargs