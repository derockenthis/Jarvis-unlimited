from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from app.agent.provider_config import ProviderRuntimeConfig
from app.services.mcp_service import McpService

PLAYWRIGHT_TOOL_PREFIX = "browser_"

PLAYWRIGHT_BUNDLES: dict[str, frozenset[str] | None] = {
    "off": frozenset(),
    "core": frozenset(
        {
            "browser_navigate",
            "browser_snapshot",
            "browser_click",
            "browser_type",
            "browser_press_key",
            "browser_select_option",
            "browser_wait_for",
            "browser_tabs",
        }
    ),
    "read": frozenset(
        {
            "browser_navigate",
            "browser_snapshot",
            "browser_click",
            "browser_hover",
            "browser_press_key",
            "browser_select_option",
            "browser_tabs",
            "browser_wait_for",
            "browser_take_screenshot",
            "browser_navigate_back",
            "browser_console_messages",
            "browser_network_requests",
            "browser_network_request",
        }
    ),
    "form": frozenset(
        {
            "browser_navigate",
            "browser_snapshot",
            "browser_click",
            "browser_type",
            "browser_fill_form",
            "browser_select_option",
            "browser_press_key",
            "browser_wait_for",
            "browser_file_upload",
            "browser_drop",
            "browser_tabs",
            "browser_take_screenshot",
        }
    ),
    "full": None,
}

_BROWSER_INTENT_TERMS = (
    "browser",
    "playwright",
    "website",
    "web page",
    "webpage",
    "search",
    "look for",
    "find",
    "google",
    "url",
    "navigate",
    "open page",
    "click",
    "form",
    "fill",
    "input",
    "button",
    "link",
    "tab",
    "screenshot",
    "snapshot",
    "scrape",
    "extract",
    "dom",
    "html",
    "selector",
    "http://",
    "https://",
)

_DOMAIN_PATTERN = re.compile(r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}\b")


@dataclass(frozen=True, slots=True)
class SelectedMcpTools:
    tools: list[object]
    total_resolved: int
    playwright_resolved: int
    playwright_selected: int
    playwright_bundle: str
    browser_intent: bool
    composite_tool_enabled: bool


def _has_browser_intent(message: str) -> bool:
    normalized = message.strip().lower()
    return any(term in normalized for term in _BROWSER_INTENT_TERMS) or bool(
        _DOMAIN_PATTERN.search(normalized)
    )


def _playwright_bundle_for_request(
    provider_config: ProviderRuntimeConfig, message: str
) -> tuple[str, bool]:
    browser_intent = _has_browser_intent(message)
    if not browser_intent:
        return "off", browser_intent

    normalized = message.lower()
    if provider_config.provider != "ollama":
        if any(term in normalized for term in ("form", "fill", "upload", "drop", "select")):
            return "form", browser_intent
    return provider_config.playwright_bundle, browser_intent


def _extract_tool_name(tool: object) -> str:
    return str(getattr(tool, "name", ""))


def _is_playwright_tool(tool: object) -> bool:
    return _extract_tool_name(tool).startswith(PLAYWRIGHT_TOOL_PREFIX)


def _filter_playwright_tools(tools: list[object], bundle: str) -> list[object]:
    allowed_names = PLAYWRIGHT_BUNDLES.get(bundle)
    if allowed_names is None:
        return list(tools)
    return [tool for tool in tools if _extract_tool_name(tool) in allowed_names]


def _extract_text_content(result: Any) -> str | None:
    if isinstance(result, dict):
        content = result.get("content")
        if isinstance(content, list):
            text_parts = [
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and item.get("type") == "text"
            ]
            combined = "\n".join(part for part in text_parts if part).strip()
            return combined or None
        if "data" in result:
            return str(result["data"])
    return None if result is None else str(result)


def _build_browser_open_and_inspect_tool(playwright_tools: list[object]) -> object | None:
    tool_map = {_extract_tool_name(tool): tool for tool in playwright_tools}
    navigate_tool = tool_map.get("browser_navigate")
    snapshot_tool = tool_map.get("browser_snapshot")
    screenshot_tool = tool_map.get("browser_take_screenshot")
    wait_tool = tool_map.get("browser_wait_for")
    if navigate_tool is None or snapshot_tool is None:
        return None

    async def browser_open_and_inspect_tool(
        url: str,
        wait_for_text: str = "",
        wait_for_seconds: float = 0,
        include_snapshot: bool = True,
        include_screenshot: bool = True,
        full_page_screenshot: bool = False,
        tool_context: object | None = None,
    ) -> dict[str, Any]:
        """Open a page and capture its current state in one compact tool call.

        Args:
            url: The page URL to open.
            wait_for_text: Optional text to wait for after navigation.
            wait_for_seconds: Optional number of seconds to wait after navigation.
            include_snapshot: Whether to capture a markdown page snapshot.
            include_screenshot: Whether to capture a screenshot.
            full_page_screenshot: Whether the screenshot should include the full page.

        Returns:
            A dictionary with the navigation result and any captured page artifacts.
        """

        navigation = await navigate_tool.run_async(args={"url": url}, tool_context=tool_context)
        steps: list[dict[str, Any]] = [{"tool": "browser_navigate", "result": navigation}]
        waited = None
        if wait_tool is not None:
            if wait_for_text.strip():
                waited = await wait_tool.run_async(
                    args={"text": wait_for_text.strip()}, tool_context=tool_context
                )
                steps.append({"tool": "browser_wait_for", "result": waited})
            elif wait_for_seconds > 0:
                waited = await wait_tool.run_async(
                    args={"time": wait_for_seconds}, tool_context=tool_context
                )
                steps.append({"tool": "browser_wait_for", "result": waited})

        snapshot_result = None
        if include_snapshot:
            snapshot_result = await snapshot_tool.run_async(args={}, tool_context=tool_context)
            steps.append({"tool": "browser_snapshot", "result": snapshot_result})

        screenshot_result = None
        if include_screenshot and screenshot_tool is not None:
            screenshot_result = await screenshot_tool.run_async(
                args={"type": "png", "fullPage": full_page_screenshot},
                tool_context=tool_context,
            )
            steps.append({"tool": "browser_take_screenshot", "result": screenshot_result})

        return {
            "status": "success",
            "data": {
                "url": url,
                "navigation": navigation,
                "wait": waited,
                "snapshot": _extract_text_content(snapshot_result),
                "screenshot": _extract_text_content(screenshot_result),
                "steps": steps,
            },
        }

    return browser_open_and_inspect_tool


async def select_mcp_tools(
    mcp_service: McpService,
    provider_config: ProviderRuntimeConfig,
    message: str,
    conversation_context: str = "",
) -> SelectedMcpTools:
    """Resolve MCP tools and expose only the request-scoped subset for the agent."""

    resolved_tools = await mcp_service.resolve_running_tools()
    playwright_tools = [tool for tool in resolved_tools if _is_playwright_tool(tool)]
    non_playwright_tools = [tool for tool in resolved_tools if not _is_playwright_tool(tool)]

    intent_source = f"{message}\n{conversation_context}".strip()
    bundle, browser_intent = _playwright_bundle_for_request(provider_config, intent_source)
    selected_playwright_tools = _filter_playwright_tools(playwright_tools, bundle)

    composite_tool = None
    if browser_intent and provider_config.prefers_compact_browser_tools and playwright_tools:
        composite_tool = _build_browser_open_and_inspect_tool(playwright_tools)

    tools = list(non_playwright_tools)
    if composite_tool is not None:
        tools.append(composite_tool)
    tools.extend(selected_playwright_tools)

    return SelectedMcpTools(
        tools=tools,
        total_resolved=len(resolved_tools),
        playwright_resolved=len(playwright_tools),
        playwright_selected=len(selected_playwright_tools),
        playwright_bundle=bundle,
        browser_intent=browser_intent,
        composite_tool_enabled=composite_tool is not None,
    )


async def build_mcp_tools(
    mcp_service: McpService,
    provider_config: ProviderRuntimeConfig,
    message: str,
) -> list[object]:
    """Resolve the currently enabled ADK MCP tools for a chat run."""

    selection = await select_mcp_tools(mcp_service, provider_config, message)
    return selection.tools
