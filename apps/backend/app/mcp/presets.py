from app.schemas import McpToolConfig


def _build_playwright_preset(*, shared_browser_context: bool) -> McpToolConfig:
    args = [
        "@playwright/mcp@latest",
        "--browser=chrome",
        "--caps=vision",
        "--timeout-action=10000",
        "--timeout-navigation=90000",
        "--output-dir=data/playwright-output",
    ]
    if shared_browser_context:
        args.insert(3, "--shared-browser-context")

    return McpToolConfig(
        id="playwright",
        name="Playwright",
        command="npx",
        args=args,
        enabled=True,
        auto_start=True,
        status="running",
        description="Browser automation MCP preset for agent web browsing and preview checks.",
    )


PLAYWRIGHT_MCP_PRESET = _build_playwright_preset(shared_browser_context=True)
PLAYWRIGHT_MCP_ISOLATED_PRESET = _build_playwright_preset(shared_browser_context=False)
