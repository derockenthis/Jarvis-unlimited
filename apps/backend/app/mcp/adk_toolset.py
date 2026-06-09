from app.schemas import McpToolConfig


def build_mcp_toolset(config: McpToolConfig) -> object:
    """Build an ADK McpToolset for a local stdio MCP server."""

    from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
    from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
    from mcp import StdioServerParameters

    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(command=config.command, args=config.args),
            timeout=60.0,
        )
    )


def build_running_mcp_toolsets(configs: list[McpToolConfig]) -> list[object]:
    """Build ADK MCP toolsets for enabled tools the user marked as running."""

    return [
        build_mcp_toolset(config)
        for config in configs
        if config.enabled and config.status == "running"
    ]


async def resolve_running_mcp_tools(configs: list[McpToolConfig]) -> list[object]:
    """Resolve concrete MCP tools for enabled tools the user marked as running."""

    tools: list[object] = []
    for toolset in build_running_mcp_toolsets(configs):
        tools.extend(await toolset.get_tools())
    return tools
