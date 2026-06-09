from app.schemas import McpToolConfig


PLAYWRIGHT_MCP_PRESET = McpToolConfig(
    id="playwright",
    name="Playwright",
    command="npx",
    args=[
        "@playwright/mcp@latest",
        "--browser=chrome",
        "--caps=vision",
        "--shared-browser-context",
        "--timeout-action=10000",
        "--timeout-navigation=90000",
        "--output-dir=data/playwright-output",
    ],
    enabled=True,
    auto_start=True,
    status="running",
    description="Browser automation MCP preset for agent web browsing and preview checks.",
)
