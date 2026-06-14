# Backend Tools And Security

## Scope

This document explains the local tools Jarvis can expose to the ADK agent and the policies that constrain them.

Primary files:

| File | Role |
| --- | --- |
| `apps/backend/app/tools/agent_tools.py` | ADK-facing wrappers for file, search, and edit tools. |
| `apps/backend/app/tools/file_explorer.py` | Directory listing and bounded folder tree traversal. |
| `apps/backend/app/tools/search_tools.py` | Bounded file reads and ripgrep search. |
| `apps/backend/app/tools/edit_tools.py` | File creation, replacement, insertion, and diffs. |
| `apps/backend/app/tools/terminal_tools.py` | ADK-facing wrappers for guarded terminal sessions. |
| `apps/backend/app/tools/vision_tools.py` | ADK-facing wrappers for desktop screenshot and image analysis. |
| `apps/backend/app/tools/memory_tools.py` | ADK-facing wrappers for memory status and node reads. |
| `apps/backend/app/tools/models.py` | Shared `ToolResult` model. |
| `apps/backend/app/security/path_policy.py` | Filesystem path access policy. |
| `apps/backend/app/security/command_policy.py` | Terminal command allowlist and syntax policy. |
| `apps/backend/app/services/session_terminal_service.py` | Persistent terminal session service. |
| `apps/backend/app/services/desktop_vision_service.py` | Screenshot and local image analysis service. |

## Tool Design Pattern

Tool code follows a two-layer pattern:

1. Core tool functions receive concrete dependencies such as `PathPolicy` and return `ToolResult`.
2. ADK wrapper builders close over dependencies and expose model-facing callables that return plain dictionaries.

For example, `read_file_section(...)` is testable directly, while `read_file_section_tool(...)` is the ADK-facing wrapper created by `build_agent_tools(policy)`.

This keeps tests independent from ADK internals and keeps path validation close to every local operation.

## Path Policy

`PathPolicy.resolve_allowed(...)` resolves the requested path before deciding whether access is allowed.

Modes:

| Mode | Behavior |
| --- | --- |
| `full_access=True` | Any resolved path is allowed. |
| `full_access=False` | Path must be equal to or inside one of the configured allowed roots. |

The policy expands `~`, resolves symlinks, and then checks ancestors. In scoped mode this prevents path traversal and symlink escapes from leaving the granted roots.

## File Explorer Tools

`list_directory(path, policy)`:

1. Resolves the directory through `PathPolicy`.
2. Rejects non-directories.
3. Lists immediate children sorted case-insensitively.
4. Skips `.git`, `node_modules`, `__pycache__`, and `.venv`.
5. Returns each child name, path, type, and size.

`folder_tree(path, max_depth, max_entries, policy)`:

1. Resolves the root through `PathPolicy`.
2. Recursively walks children with a depth cap and entry cap.
3. Uses the same skip list as `list_directory`.
4. Returns path, name, depth, and type for each entry.

## Search And Read Tools

`read_file_section(path, start_line, end_line, policy)`:

1. Resolves the path.
2. Requires a file.
3. Requires a valid 1-based inclusive line range.
4. Rejects files larger than 1 MB.
5. Rejects binary-looking files by checking for NUL bytes in the first 4096 bytes.
6. Decodes UTF-8 with replacement and returns selected lines.

`ripgrep_search(query, root, max_results, policy)`:

1. Requires `rg` on PATH.
2. Resolves the root through `PathPolicy`.
3. Runs `rg` with `subprocess.run` and no shell.
4. Includes line number, column, filename, no color, timeout, and result cap.
5. Returns a clear diagnostic if ripgrep is missing.

## Edit Tools

`create_file(path, content, overwrite, policy)`:

1. Resolves the target path.
2. Fails if the file exists and `overwrite` is false.
3. Creates parent directories.
4. Writes UTF-8 text.
5. Returns a unified diff.

`replace_file_section(path, start_line, end_line, replacement, policy)`:

1. Resolves and reads the target file.
2. Requires a valid 1-based inclusive range inside the file.
3. Replaces that range with `replacement.splitlines()`.
4. Writes the resulting file with a trailing newline.
5. Returns a unified diff.

`insert_at_line(path, line, content, policy)`:

1. Resolves and reads the target file.
2. Requires a valid 1-based insertion point.
3. Inserts `content.splitlines()` before that line.
4. Writes the resulting file with a trailing newline.
5. Returns a unified diff.

Current limitation: edit tools do not yet provide user confirmation or conflict detection beyond line ranges and overwrite flags.

## Command Policy

`CommandPolicy.parse(command)` rejects commands before any subprocess starts if:

1. The command is empty.
2. It contains shell control characters such as `;`, `&`, `|`, `>`, `<`, backticks, `$`, parentheses, braces, brackets, or newlines.
3. The executable is a path instead of a bare executable name.
4. The executable is not on the allowlist.
5. The command is `git` with a non-read-only subcommand.

Allowed executables currently include common read/inspect tools plus `node`, `npm`, `pytest`, `python`, `python3`, `rg`, and `uv`. Git is limited to `branch`, `diff`, `log`, `show`, and `status`.

## Terminal Session Service

`SessionTerminalService` provides guarded, persistent terminal sessions keyed by `user_id`, `session_id`, and generated `terminal_id`.

Operations:

| Operation | Behavior |
| --- | --- |
| `spawn(...)` | Validates cwd through `PathPolicy`, creates a `TerminalSession`, and returns its id. |
| `run(...)` | Validates command through `CommandPolicy`, runs it with no shell, captures output, caps output, and stores the result. |
| `read(...)` | Returns cwd and the previous result. |
| `close(...)` | Removes the session. |

Special handling:

1. `cd` is handled internally and must receive exactly one path.
2. Relative `cd` targets are resolved against the current terminal cwd.
3. Commands time out after 20 seconds.
4. stdout/stderr are truncated at 8000 characters.

This is not an unrestricted shell. It is a constrained development and inspection tool.

## Vision Tools

`DesktopVisionService.capture_desktop_screenshot(name)`:

1. Sanitizes the screenshot name.
2. Writes a PNG under `Settings.screenshot_dir`.
3. Uses macOS `screencapture -x`.
4. Returns the saved path or error output.

`DesktopVisionService.analyze_image(path, prompt, policy)`:

1. Resolves the local image path through `PathPolicy`.
2. Reads and base64-encodes the image.
3. Sends a multimodal request through LiteLLM using OpenRouter vision settings.
4. Returns the model analysis text.

Vision tools are attached to the ADK agent only for chat requests with screen-sharing enabled.

## Memory Tools

Memory tools expose inspection only:

1. Memory status.
2. Read a durable memory node by id.

They do not let the live agent directly create, update, link, or deprecate durable graph nodes.

## Revision Notes

1. Add confirmation support before sensitive edits once the UI has an approval flow.
2. Add a read-only git diff tool if the product needs user review without letting the agent run arbitrary git commands.
3. Consider moving common skip patterns and size limits into settings if users need project-specific tuning.