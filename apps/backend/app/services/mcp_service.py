from app.mcp.adk_toolset import build_mcp_toolset
from app.mcp.presets import PLAYWRIGHT_MCP_PRESET
from app.schemas import McpActionRequest, McpActionResponse, McpToolConfig


class McpService:
    """In-memory MCP registry for ADK-managed MCP toolsets."""

    def __init__(self, *, playwright_preset: McpToolConfig = PLAYWRIGHT_MCP_PRESET) -> None:
        self._tools: dict[str, McpToolConfig] = {playwright_preset.id: playwright_preset}
        self._manually_stopped_tool_ids: set[str] = set()
        self._toolsets: dict[str, object] = {}
        self._toolset_fingerprints: dict[str, tuple[str, tuple[str, ...]]] = {}

    def list_tools(self) -> list[McpToolConfig]:
        return list(self._tools.values())

    def ensure_auto_started_tools(self) -> list[McpToolConfig]:
        """Mark enabled auto-start tools running before ADK resolves their toolsets."""

        for tool_id, tool in list(self._tools.items()):
            if (
                tool.enabled
                and tool.auto_start
                and tool.status == "stopped"
                and tool_id not in self._manually_stopped_tool_ids
            ):
                self._tools[tool_id] = tool.model_copy(update={"status": "running"})
        return self.list_tools()

    def get_tool(self, tool_id: str) -> McpToolConfig | None:
        return self._tools.get(tool_id)

    async def resolve_running_tools(self) -> list[object]:
        tools: list[object] = []
        running_ids: set[str] = set()

        for config in self.ensure_auto_started_tools():
            if not (config.enabled and config.status == "running"):
                continue

            running_ids.add(config.id)
            toolset = await self._get_or_create_toolset(config)
            tools.extend(await toolset.get_tools())

        for stale_tool_id in set(self._toolsets) - running_ids:
            await self._close_toolset(stale_tool_id)

        return tools

    async def _get_or_create_toolset(self, config: McpToolConfig) -> object:
        fingerprint = (config.command, tuple(config.args))
        cached_toolset = self._toolsets.get(config.id)
        cached_fingerprint = self._toolset_fingerprints.get(config.id)

        if cached_toolset is not None and cached_fingerprint == fingerprint:
            return cached_toolset

        if cached_toolset is not None:
            await self._close_toolset(config.id)

        toolset = build_mcp_toolset(config)
        self._toolsets[config.id] = toolset
        self._toolset_fingerprints[config.id] = fingerprint
        return toolset

    async def _close_toolset(self, tool_id: str) -> None:
        toolset = self._toolsets.pop(tool_id, None)
        self._toolset_fingerprints.pop(tool_id, None)
        close = getattr(toolset, "close", None)
        if callable(close):
            await close()

    def start_tool(self, tool_id: str, request: McpActionRequest) -> McpActionResponse:
        tool = self._tools.get(tool_id)
        if tool is None:
            return McpActionResponse(tool_id=tool_id, status="error", message="Unknown MCP tool.")

        updated = tool.model_copy(update={"status": "running"})
        self._manually_stopped_tool_ids.discard(tool_id)
        self._tools[tool_id] = updated
        return McpActionResponse(
            tool_id=tool_id,
            status=updated.status,
            message=f"{updated.name} enabled for ADK. Command: {updated.command} {' '.join(updated.args)}",
        )

    def stop_tool(self, tool_id: str, request: McpActionRequest) -> McpActionResponse:
        tool = self._tools.get(tool_id)
        if tool is None:
            return McpActionResponse(tool_id=tool_id, status="error", message="Unknown MCP tool.")

        updated = tool.model_copy(update={"status": "stopped"})
        self._manually_stopped_tool_ids.add(tool_id)
        self._tools[tool_id] = updated
        return McpActionResponse(
            tool_id=tool_id,
            status=updated.status,
            message=f"{updated.name} disabled for new ADK chat runs.",
        )
