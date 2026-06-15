from __future__ import annotations

import argparse
import json
from pathlib import Path
import asyncio
import sys
import tempfile
from typing import Any

from app.agent.agent import build_agent
from app.agent.provider_config import ProviderRuntimeConfig
from app.agent.tools.mcp import _build_browser_open_and_inspect_tool
from app.agent.tools import build_terminal_tools, build_workspace_tools
from app.config import Settings, get_settings
from app.services.mcp_service import McpService
from app.mcp.presets import PLAYWRIGHT_MCP_ISOLATED_PRESET
from app.security.path_policy import PathPolicy
from app.services.settings_service import SettingsService
from app.services.session_terminal_service import SessionTerminalService


def _build_sub_agent_instruction(name: str, description: str, tools: list[str]) -> str:
    tool_summary = ", ".join(tools)
    return "\n\n".join(
        [
            f"You are the specialized sub-agent '{name}'.",
            description.strip(),
            "Operating rules:",
            "- Follow the user task exactly.",
            "- Use your tools only when they reduce risk or save time.",
            "- Return the final result concisely and do not expose internal reasoning.",
            f"Enabled tool groups: {tool_summary}",
        ]
    )


def _browser_tool_names(tools: list[str]) -> list[str]:
    return sorted({tool for tool in tools if tool.startswith("browser_")})


async def _build_sub_agent_tools(policy: PathPolicy, tools: list[str], name: str) -> list[object]:
    resolved_tools: list[object] = []
    if "filesystem" in tools:
        resolved_tools.extend(build_workspace_tools(policy))
    if "terminal" in tools:
        terminal_service = SessionTerminalService()
        resolved_tools.extend(
            build_terminal_tools(
                terminal_service,
                policy,
                user_id="sub-agent",
                session_id=name,
            )
        )
    browser_tools = _browser_tool_names(tools)
    if browser_tools:
        mcp_service = McpService(playwright_preset=PLAYWRIGHT_MCP_ISOLATED_PRESET)
        resolved_browser_tools = await _resolve_browser_tools(mcp_service, browser_tools)
        resolved_tools.extend(resolved_browser_tools)
    return resolved_tools


def _sub_agent_provider_config(settings: Settings) -> ProviderRuntimeConfig:
    model_settings = SettingsService(settings).get_model_settings()
    current_provider = (model_settings.current_provider or "openrouter").strip().lower()
    provider_row = next(
        (row for row in model_settings.providers if row.provider.strip().lower() == current_provider),
        None,
    )

    if provider_row is not None:
        return ProviderRuntimeConfig(
            provider=current_provider,
            model_name=provider_row.model or None,
            api_key=provider_row.api_key or None,
            base_url=provider_row.base_url or None,
        )

    if current_provider == "openrouter":
        return ProviderRuntimeConfig(
            provider=current_provider,
            model_name=settings.openrouter_model,
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )

    return ProviderRuntimeConfig(provider=current_provider)


async def _resolve_browser_tools(mcp_service: McpService, requested_names: list[str]) -> list[object]:
    resolved_tools = await mcp_service.resolve_running_tools()
    browser_tools = [
        tool
        for tool in resolved_tools
        if str(getattr(tool, "name", "")).startswith("browser_")
    ]
    browser_tool_map = {str(getattr(tool, "name", "")): tool for tool in browser_tools}

    resolved: list[object] = []
    missing = [name for name in requested_names if name not in browser_tool_map]
    if "browser_open_and_inspect_tool" in missing:
        composite_tool = _build_browser_open_and_inspect_tool(browser_tools)
        if composite_tool is not None:
            resolved.append(composite_tool)
            missing = [name for name in missing if name != "browser_open_and_inspect_tool"]

    if missing:
        raise ValueError(
            "Requested browser tools are unavailable: " + ", ".join(sorted(missing)) + "."
        )

    for name in requested_names:
        if name == "browser_open_and_inspect_tool":
            continue
        resolved.append(browser_tool_map[name])

    return resolved


async def _run_sub_agent(spec: dict[str, Any]) -> int:
    settings = get_settings()
    policy = PathPolicy(settings.allowed_root_paths, full_access=settings.full_filesystem_access)
    provider_config = _sub_agent_provider_config(settings)

    tools = await _build_sub_agent_tools(policy, spec["tools"], spec["name"])
    instruction = _build_sub_agent_instruction(spec["name"], spec["description"], spec["tools"])

    agent = build_agent(
        settings=settings,
        tools=tools,
        conversation_context=None,
        provider_config=provider_config,
        skills_root=None,
        instruction_override=instruction,
        agent_name=spec["name"],
        agent_description=spec["description"],
    )

    from google.adk.apps.app import App
    from google.adk.runners import Runner
    from google.adk.sessions.sqlite_session_service import SqliteSessionService
    from google.genai import types

    with tempfile.TemporaryDirectory(prefix=f"{spec['name']}-launcher-") as temp_dir:
        session_db = Path(temp_dir) / "sub_agent.sqlite"
        session_service = SqliteSessionService(str(session_db))
        app = App(name=f"{spec['name']}_launcher", root_agent=agent)
        runner = Runner(app=app, session_service=session_service)
        await session_service.create_session(
            app_name=f"{spec['name']}_launcher",
            user_id="sub-agent",
            session_id=spec["name"],
        )
        new_message = types.Content(
            role="user",
            parts=[types.Part.from_text(text=spec["instructions"])],
        )

        final_text = ""
        async for event in runner.run_async(
            user_id="sub-agent",
            session_id=spec["name"],
            new_message=new_message,
        ):
            content = getattr(event, "content", None)
            if content is None or not getattr(content, "parts", None):
                continue
            for part in content.parts:
                text = getattr(part, "text", None)
                if text and not getattr(part, "thought", False):
                    final_text = text

        print(
            json.dumps(
                {
                    "status": "success",
                    "name": spec["name"],
                    "result": final_text,
                    "tools": spec["tools"],
                },
                ensure_ascii=True,
            )
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch a specialized local sub-agent.")
    parser.add_argument("--spec-file", required=True)
    args = parser.parse_args()

    spec = json.loads(Path(args.spec_file).read_text(encoding="utf-8"))
    try:
        return asyncio.run(_run_sub_agent(spec))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
