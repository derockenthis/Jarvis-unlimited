from pathlib import Path
from collections.abc import Sequence


BASE_INSTRUCTION = """You are Jarvis, a local-first desktop AI assistant running on the user's machine.

Working style:
- Act directly. Keep internal planning minimal and only as long as needed to choose the next safe step.
- Prefer short, task-focused answers over extended reasoning.
- Prefer using your tools to gather real facts about the filesystem instead of guessing. Use list_directory_tool and folder_tree_tool to explore, read_file_section_tool to read code, and search_files_tool to find text.
- When you need to inspect the user's desktop or a local image, use capture_desktop_screenshot_tool to save a screenshot and analyze_image_tool to reason about what is visible in that image. These tools are available only when the user has enabled screen sharing; take screenshots only when visual context is necessary or likely changed.
- When browser automation tools are available through MCP, use them for real web interactions instead of pretending you browsed. Use only the exact browser tool names listed for the current run. Do not invent browser tool names or assume a missing browser capability exists.
- Only use capture_desktop_screenshot_tool or analyze_image_tool when those tools are actually available for the current request. They are absent on normal web-browsing turns unless screen sharing is enabled.
- When terminal tools are available, use them only for safe development and inspection tasks. Respect their command policy and persist the same terminal session when the user asks you to continue using it.
- When memory tools are available, you may inspect durable memory status or read a memory node, but do not claim durable memory is fully automated unless the tools actually show nodes and observations.
- When the user asks you to change files, make the smallest safe edit with create_file_tool, replace_file_section_tool, or insert_at_line_tool, and confirm what changed.
- Always pass absolute paths to tools. If you do not know a path, discover it with the exploration tools first.
- If a tool returns an error, read the message, adjust, and try a corrected call rather than repeating the same request.
- Do not output hidden reasoning, channel markers, or internal protocol tokens in the final answer. Keep the user-visible response clean and concise.

Safety:
- Only operate inside paths the user has granted. Never fabricate file contents or tool results. Be concise and explain what you did."""


def _tool_name(tool: object) -> str:
    return str(getattr(tool, "name", getattr(tool, "__name__", "")))


def _browser_tool_names(tools: Sequence[object] | None) -> list[str]:
    if not tools:
        return []
    names = {_tool_name(tool) for tool in tools}
    return sorted(name for name in names if name.startswith("browser_"))


def build_browser_tool_guidance(tools: Sequence[object] | None) -> str | None:
    browser_tool_names = _browser_tool_names(tools)
    if not browser_tool_names:
        return None

    guidance = [
        "Browser tool manifest for this run:",
        f"- Use only these exact browser tool names: {', '.join(browser_tool_names)}.",
        "- Never call a browser tool that is not listed here.",
    ]

    if "browser_open_and_inspect_tool" in browser_tool_names:
        guidance.append(
            "- Prefer browser_open_and_inspect_tool to open a page and capture its current state before taking smaller browser actions."
        )
    if "browser_snapshot" in browser_tool_names:
        guidance.append(
            "- Prefer browser_snapshot before clicking so your next selector or element reference is grounded in the current page state."
        )
    if "browser_type" not in browser_tool_names:
        guidance.append(
            "- There is no text-entry browser tool in this run. Do not invent browser_type or browser_fill_form."
        )
        if "browser_press_key" in browser_tool_names:
            guidance.append(
                "- browser_press_key is only for keys like Enter, Tab, Escape, arrows, and shortcuts. It is not a substitute for typing arbitrary text."
            )
    if "browser_evaluate" in browser_tool_names:
        guidance.append(
            "- For browser_evaluate, pass a plain browser-side function that uses DOM APIs directly. Do not wrap it as async(page) => ... and do not call page.evaluate inside browser_evaluate."
        )
    if "browser_run_code_unsafe" in browser_tool_names:
        guidance.append(
            "- For browser_run_code_unsafe, the provided code already receives the Playwright page object."
        )

    return "\n".join(guidance)


def build_instruction(skills_root: str | None, tools: Sequence[object] | None = None) -> str:
    parts = [BASE_INSTRUCTION]
    browser_guidance = build_browser_tool_guidance(tools)
    if browser_guidance:
        parts.append(browser_guidance)
    if skills_root:
        selected_root = Path(skills_root).expanduser().resolve()
        skills_md = selected_root / "skills.md"
        parts.append(
            "\n".join(
                [
                    "Skills library:",
                    f"- The user selected skills folder is {selected_root}.",
                    "- Search this folder first when the user asks about skills, reusable workflows, or prompts.",
                    f"- If {skills_md} exists, treat it as the canonical skills index.",
                    f"- If the user asks to add or update a skill, prefer editing or creating {skills_md}.",
                ]
            )
        )
    return "\n\n".join(parts)


def append_conversation_context(
    instruction: str, conversation_context: str | None
) -> str:
    if not conversation_context:
        return instruction
    return "\n\n".join(
        [
            instruction,
            "Conversation context cache:",
            conversation_context,
            "Use this cached context as the compact session memory for the current turn.",
        ]
    )