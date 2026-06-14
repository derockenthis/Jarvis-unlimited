from collections.abc import Sequence

from app.agent.provider_config import ProviderRuntimeConfig
from app.agent.prompt import append_conversation_context, build_instruction
from app.agent.tools import build_workspace_tools
from app.config import Settings
from app.config import get_settings
from app.security.path_policy import PathPolicy


def build_agent(
    settings: Settings,
    tools: Sequence[object] | None = None,
    skills_root: str | None = None,
    conversation_context: str | None = None,
    provider_config: ProviderRuntimeConfig | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> object:
    """Build the Jarvis ADK root agent."""

    from google.adk.agents import Agent
    from google.adk.models.lite_llm import LiteLlm

    resolved_provider_config = provider_config or ProviderRuntimeConfig(
        provider=provider or "openrouter",
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
    )

    return Agent(
        name="jarvis_desktop_agent",
        model=LiteLlm(
            model=resolved_provider_config.litellm_model(settings),
            **resolved_provider_config.litellm_kwargs(settings),
        ),
        description="Local-first desktop assistant for filesystem, terminal, memory, and MCP-assisted tasks.",
        instruction=append_conversation_context(
            build_instruction(skills_root, tools=tools), conversation_context
        ),
        tools=list(tools or []),
    )


def build_root_agent(
    settings: Settings,
    tools: Sequence[object] | None = None,
    skills_root: str | None = None,
    conversation_context: str | None = None,
    provider_config: ProviderRuntimeConfig | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> object:
    """Backward-compatible alias for existing imports."""

    return build_agent(
        settings=settings,
        tools=tools,
        skills_root=skills_root,
        conversation_context=conversation_context,
        provider_config=provider_config,
        provider=provider,
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
    )


def build_default_agent(settings: Settings | None = None) -> object:
    """Build a stable ADK-loadable agent for local smoke tests and eval wiring."""

    resolved_settings = settings or get_settings()
    policy = PathPolicy(
        resolved_settings.allowed_root_paths,
        full_access=resolved_settings.full_filesystem_access,
    )
    return build_agent(
        settings=resolved_settings,
        tools=build_workspace_tools(policy),
    )


async def get_agent_async() -> tuple[object, None]:
    """ADK loader hook used by evaluators and other agent tooling."""

    return build_default_agent(), None