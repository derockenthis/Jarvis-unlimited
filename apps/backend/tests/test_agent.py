import app.agent.agent as agent_module

from app.agent.provider_config import ProviderRuntimeConfig
from app.agent.prompt import build_instruction
from app.agent.tools.mcp import select_mcp_tools
from app.config import Settings


def test_provider_runtime_config_validates_openrouter_and_ollama_support() -> None:
    settings = Settings(OPENROUTER_API_KEY="")

    openrouter = ProviderRuntimeConfig()
    ollama = ProviderRuntimeConfig(provider="Ollama", model_name="gemma4:12b")

    assert openrouter.missing_configuration(settings) == (
        "OpenRouter is not configured. Enter an OpenRouter API key or set OPENROUTER_API_KEY."
    )
    assert ollama.missing_configuration(settings) is None
    assert ollama.supports_adk_tools is True


def test_provider_runtime_config_resolves_litellm_models() -> None:
    settings = Settings(OPENROUTER_MODEL="google/gemma-4-26b-a4b-it")

    openrouter = ProviderRuntimeConfig(provider="openrouter", model_name="anthropic/claude-sonnet-4")
    openai = ProviderRuntimeConfig(provider="openai", model_name="gpt-4.1-mini")
    ollama = ProviderRuntimeConfig(provider="ollama", model_name="gemma4:12b")

    assert openrouter.litellm_model(settings) == "openrouter/anthropic/claude-sonnet-4"
    assert openai.litellm_model(settings) == "openai/gpt-4.1-mini"
    assert ollama.litellm_model(settings) == "ollama_chat/gemma4:12b"


def test_provider_runtime_config_builds_litellm_kwargs_without_env_mutation() -> None:
    settings = Settings(
        OPENROUTER_API_KEY="router-key",
        OPENROUTER_API_BASE="https://openrouter.example/v1",
    )

    openrouter = ProviderRuntimeConfig(provider="openrouter")
    openai = ProviderRuntimeConfig(
        provider="openai",
        api_key="openai-key",
        base_url="https://openai.example/v1",
    )
    ollama = ProviderRuntimeConfig(provider="ollama", base_url="http://ollama.internal:11434")

    assert openrouter.litellm_kwargs(settings) == {
        "api_key": "router-key",
        "api_base": "https://openrouter.example/v1",
    }
    assert openai.litellm_kwargs(settings) == {
        "api_key": "openai-key",
        "api_base": "https://openai.example/v1",
    }
    assert ollama.litellm_kwargs(settings) == {
        "api_base": "http://ollama.internal:11434",
        "custom_llm_provider": "ollama_chat",
        "extra_body": {"options": {"num_ctx": 50000}},
    }


def test_provider_runtime_config_exposes_playwright_profiles() -> None:
    openrouter = ProviderRuntimeConfig(provider="openrouter")
    ollama = ProviderRuntimeConfig(provider="ollama", model_name="gemma4:12b")

    assert openrouter.playwright_bundle == "read"
    assert openrouter.prefers_compact_browser_tools is False
    assert ollama.playwright_bundle == "core"
    assert ollama.prefers_compact_browser_tools is True


class _FakeMcpTool:
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[dict[str, object]] = []

    async def run_async(self, *, args: dict[str, object], tool_context: object) -> dict[str, object]:
        self.calls.append({"args": args, "tool_context": tool_context})
        return {
            "status": "success",
            "content": [{"type": "text", "text": f"{self.name}:{args}"}],
        }


class _FakeMcpService:
    def __init__(self, tools: list[object]) -> None:
        self._tools = tools

    async def resolve_running_tools(self) -> list[object]:
        return list(self._tools)


async def test_select_mcp_tools_skips_playwright_without_browser_intent() -> None:
    service = _FakeMcpService(
        [
            _FakeMcpTool("browser_navigate"),
            _FakeMcpTool("browser_snapshot"),
            _FakeMcpTool("workspace_list"),
        ]
    )

    selection = await select_mcp_tools(
        service,
        ProviderRuntimeConfig(provider="ollama", model_name="gemma4:12b"),
        "hello there",
    )

    assert selection.browser_intent is False
    assert selection.playwright_bundle == "off"
    assert selection.playwright_selected == 0
    assert [getattr(tool, "name", getattr(tool, "__name__", "")) for tool in selection.tools] == [
        "workspace_list"
    ]


async def test_select_mcp_tools_uses_compact_ollama_browser_bundle() -> None:
    service = _FakeMcpService(
        [
            _FakeMcpTool("browser_navigate"),
            _FakeMcpTool("browser_snapshot"),
            _FakeMcpTool("browser_take_screenshot"),
            _FakeMcpTool("browser_wait_for"),
            _FakeMcpTool("browser_click"),
            _FakeMcpTool("browser_type"),
            _FakeMcpTool("browser_press_key"),
            _FakeMcpTool("browser_select_option"),
            _FakeMcpTool("browser_tabs"),
            _FakeMcpTool("browser_resize"),
        ]
    )

    selection = await select_mcp_tools(
        service,
        ProviderRuntimeConfig(provider="ollama", model_name="gemma4:12b"),
        "open https://example.com and inspect the page",
    )

    names = [getattr(tool, "name", getattr(tool, "__name__", "")) for tool in selection.tools]

    assert selection.browser_intent is True
    assert selection.playwright_bundle == "core"
    assert selection.composite_tool_enabled is True
    assert names[0] == "browser_open_and_inspect_tool"
    assert "browser_resize" not in names
    assert "browser_navigate" in names


async def test_select_mcp_tools_detects_bare_domain_browser_prompt() -> None:
    service = _FakeMcpService(
        [
            _FakeMcpTool("browser_navigate"),
            _FakeMcpTool("browser_snapshot"),
            _FakeMcpTool("browser_wait_for"),
            _FakeMcpTool("browser_click"),
            _FakeMcpTool("browser_type"),
            _FakeMcpTool("browser_press_key"),
            _FakeMcpTool("browser_select_option"),
            _FakeMcpTool("browser_tabs"),
        ]
    )

    selection = await select_mcp_tools(
        service,
        ProviderRuntimeConfig(provider="ollama", model_name="gemma4:12b"),
        "open google.com",
    )

    names = [getattr(tool, "name", getattr(tool, "__name__", "")) for tool in selection.tools]

    assert selection.browser_intent is True
    assert selection.playwright_bundle == "core"
    assert "browser_navigate" in names


async def test_select_mcp_tools_detects_search_followup_browser_prompt() -> None:
    service = _FakeMcpService(
        [
            _FakeMcpTool("browser_navigate"),
            _FakeMcpTool("browser_snapshot"),
            _FakeMcpTool("browser_wait_for"),
            _FakeMcpTool("browser_click"),
            _FakeMcpTool("browser_type"),
            _FakeMcpTool("browser_press_key"),
            _FakeMcpTool("browser_select_option"),
            _FakeMcpTool("browser_tabs"),
        ]
    )

    selection = await select_mcp_tools(
        service,
        ProviderRuntimeConfig(provider="ollama", model_name="gemma4:12b"),
        "search for ducks",
    )

    names = [getattr(tool, "name", getattr(tool, "__name__", "")) for tool in selection.tools]

    assert selection.browser_intent is True
    assert selection.playwright_bundle == "core"
    assert "browser_navigate" in names


async def test_select_mcp_tools_uses_conversation_context_for_browser_followup() -> None:
    service = _FakeMcpService(
        [
            _FakeMcpTool("browser_navigate"),
            _FakeMcpTool("browser_snapshot"),
            _FakeMcpTool("browser_click"),
            _FakeMcpTool("browser_type"),
            _FakeMcpTool("browser_press_key"),
            _FakeMcpTool("browser_select_option"),
            _FakeMcpTool("browser_wait_for"),
            _FakeMcpTool("browser_tabs"),
        ]
    )

    selection = await select_mcp_tools(
        service,
        ProviderRuntimeConfig(provider="ollama", model_name="gemma4:12b"),
        "now search for ducks",
        conversation_context="Session context cache:\n- user[local-user]: open google.com",
    )

    names = [getattr(tool, "name", getattr(tool, "__name__", "")) for tool in selection.tools]

    assert selection.browser_intent is True
    assert selection.playwright_bundle == "core"
    assert "browser_navigate" in names


async def test_browser_open_and_inspect_tool_orchestrates_underlying_playwright_steps() -> None:
    navigate = _FakeMcpTool("browser_navigate")
    snapshot = _FakeMcpTool("browser_snapshot")
    screenshot = _FakeMcpTool("browser_take_screenshot")
    wait_for = _FakeMcpTool("browser_wait_for")
    service = _FakeMcpService(
        [
            navigate,
            snapshot,
            screenshot,
            wait_for,
            _FakeMcpTool("browser_click"),
            _FakeMcpTool("browser_type"),
            _FakeMcpTool("browser_press_key"),
            _FakeMcpTool("browser_select_option"),
            _FakeMcpTool("browser_tabs"),
        ]
    )

    selection = await select_mcp_tools(
        service,
        ProviderRuntimeConfig(provider="ollama", model_name="gemma4:12b"),
        "open https://example.com and inspect the page",
    )
    composite_tool = selection.tools[0]

    result = await composite_tool(
        url="https://example.com",
        wait_for_text="Example Domain",
        include_screenshot=True,
        tool_context={"session": "test"},
    )

    step_names = [step["tool"] for step in result["data"]["steps"]]

    assert step_names == [
        "browser_navigate",
        "browser_wait_for",
        "browser_snapshot",
        "browser_take_screenshot",
    ]
    assert navigate.calls == [{"args": {"url": "https://example.com"}, "tool_context": {"session": "test"}}]
    assert wait_for.calls == [
        {"args": {"text": "Example Domain"}, "tool_context": {"session": "test"}}
    ]


def test_build_instruction_lists_exact_browser_tools_for_current_run() -> None:
    instruction = build_instruction(
        None,
        tools=[
            _FakeMcpTool("browser_snapshot"),
            _FakeMcpTool("browser_click"),
            _FakeMcpTool("browser_press_key"),
            _FakeMcpTool("browser_tabs"),
        ],
    )

    assert "Use only these exact browser tool names: browser_click, browser_press_key, browser_snapshot, browser_tabs." in instruction
    assert "There is no text-entry browser tool in this run." in instruction
    assert "Do not invent browser_type or browser_fill_form." in instruction
    assert "browser_press_key is only for keys like Enter, Tab, Escape, arrows, and shortcuts." in instruction
    assert "browser_type" not in instruction.split("Use only these exact browser tool names:", 1)[1].split("\n", 1)[0]


async def test_get_agent_async_returns_default_agent_tuple(monkeypatch) -> None:
    sentinel = object()
    monkeypatch.setattr(agent_module, "build_default_agent", lambda: sentinel)

    agent, app = await agent_module.get_agent_async()

    assert agent is sentinel
    assert app is None
