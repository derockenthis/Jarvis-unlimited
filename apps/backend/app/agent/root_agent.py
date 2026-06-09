from collections.abc import Sequence
from pathlib import Path
import os

from app.config import Settings


def build_root_agent(
    settings: Settings,
    tools: Sequence[object] | None = None,
    skills_root: str | None = None,
) -> object:
    """Build the Jarvis ADK root agent.

    The import is intentionally local so health checks and tool tests still run when ADK is not
    installed yet. Live model calls require OPENROUTER_API_KEY.
    """

    from google.adk.agents import Agent
    from google.adk.models.lite_llm import LiteLlm

    if settings.google_ai_api_key:
        os.environ.setdefault("GOOGLE_API_KEY", settings.google_ai_api_key)
        os.environ.setdefault("GOOGLE_AI_API_KEY", settings.google_ai_api_key)

    if settings.openrouter_api_key:
        os.environ.setdefault("OPENROUTER_API_KEY", settings.openrouter_api_key)
        os.environ.setdefault("OPENROUTER_API_BASE", settings.openrouter_base_url)
        os.environ.setdefault("OPENAI_API_BASE", settings.openrouter_base_url)

    skills_context = ""
    if skills_root:
        selected_root = Path(skills_root).expanduser().resolve()
        skills_md = selected_root / "skills.md"
        skills_context = (
            "\nSkills library:\n"
            f"- The user selected skills folder is {selected_root}.\n"
            f"- Search this folder first when the user asks about skills, reusable workflows, or prompts.\n"
            f"- If {skills_md} exists, treat it as the canonical skills index.\n"
            f"- If the user asks to add or update a skill, prefer editing or creating {skills_md}.\n"
        )

    return Agent(
        name="jarvis_desktop_agent",
        model=LiteLlm(model=settings.openrouter_litellm_model),
        instruction=(
            "You are Jarvis, a local-first desktop AI assistant running on the user's machine.\n"
            "\n"
            "Working style:\n"
            "- Briefly think through your plan before acting, then take action.\n"
            "- Prefer using your tools to gather real facts about the filesystem instead of "
            "guessing. Use list_directory_tool and folder_tree_tool to explore, "
            "read_file_section_tool to read code, and search_files_tool to find text.\n"
            "- When you need to inspect the user's desktop or a local image, use "
            "capture_desktop_screenshot_tool to save a screenshot and analyze_image_tool to "
            "reason about what is visible in that image. These tools are available only when "
            "the user has enabled screen sharing; take screenshots only when visual context "
            "is necessary or likely changed.\n"
            "- When browser automation tools are available through MCP, use them for real web "
            "interactions instead of pretending you browsed. Prefer the exact available "
            "browser tools such as browser_navigate, browser_snapshot, browser_tabs, "
            "browser_click, browser_type, browser_wait_for, browser_evaluate, "
            "browser_run_code_unsafe, and browser_take_screenshot. Do not invent browser "
            "tool names such as browser_new_tab or browser_screenshot_tool.\n"
            "- Only use capture_desktop_screenshot_tool or analyze_image_tool when those "
            "tools are actually available for the current request. They are absent on normal "
            "web-browsing turns unless screen sharing is enabled.\n"
            "- For browser_evaluate, pass a plain browser-side function that uses DOM APIs "
            "directly. Do not wrap it as async(page) => ... and do not call page.evaluate "
            "inside browser_evaluate. For browser_run_code_unsafe, the provided code already "
            "receives the Playwright page object.\n"
            "- When terminal tools are available, use them only for safe development and "
            "inspection tasks. Respect their command policy and persist the same terminal "
            "session when the user asks you to continue using it.\n"
            "- When memory tools are available, you may inspect durable memory status or read a "
            "memory node, but do not claim durable memory is fully automated unless the tools "
            "actually show nodes and observations.\n"
            "- When the user asks you to change files, make the smallest safe edit with "
            "create_file_tool, replace_file_section_tool, or insert_at_line_tool, and confirm "
            "what changed.\n"
            f"{skills_context}"
            "- Always pass absolute paths to tools. If you do not know a path, discover it with "
            "the exploration tools first.\n"
            "- If a tool returns an error, read the message, adjust, and try a corrected call "
            "rather than repeating the same request.\n"
            "- Do not output hidden reasoning, channel markers, or internal protocol tokens in "
            "the final answer. Keep the user-visible response clean.\n"
            "\n"
            "Safety:\n"
            "- Only operate inside paths the user has granted. Never fabricate file contents or "
            "tool results. Be concise and explain what you did."
        ),
        tools=list(tools or []),
    )
