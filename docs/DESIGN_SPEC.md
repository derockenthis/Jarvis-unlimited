# Jarvis Agent Desktop Design Spec

## Overview

Jarvis Agent Desktop is a local-first desktop AI operating environment. It combines a Claude Code-style chat interface, a managed MCP tool sidebar, and a live AI work window for previews, browser sessions, generated UI, and future agent components.

The app uses Electron for the desktop shell, React and TypeScript for the renderer, FastAPI for the local backend API, and Google ADK for the agent runtime. OpenRouter provides LLM access through ADK's LiteLLM integration. SQLite is used for local session, app, and memory persistence during the prototype phase.

This is not intended to be a narrow coding bot. The long-term direction is a Jarvis-like local assistant that can inspect repositories, use MCP tools, modify code safely, preview work live, and maintain durable project knowledge through a curated memory system.

## Example Use Cases

1. A user opens a local repository and asks Jarvis to summarize its architecture. The agent lists folders, reads selected file sections, runs ripgrep searches, and returns a concise architecture map.
2. A user asks Jarvis to implement a small change. The agent searches relevant files, reads local context, applies guarded edits, returns diffs, and logs durable observations for later consolidation.
3. A user adds the Playwright MCP preset from the sidebar. Jarvis starts the MCP server and exposes browser automation tools to the ADK agent runtime.
4. A user asks Jarvis to create a UI component. The agent writes files and streams progress or preview targets into the live AI window.
5. A user asks Jarvis what is on the current desktop or in a saved screenshot. The agent captures a screenshot, analyzes the local image with a vision-capable model, and references that grounded result in chat.
6. Over time, Jarvis remembers durable project decisions, recurring gotchas, rejected approaches, and tool rules through Node-Based Agentic Memory rather than direct live-session graph writes.

## User Interface

The main window has three primary regions:

1. Collapsible sidebar for MCP tools, workspace roots, model settings, memory status, and a selectable skills folder.
2. Central chat section with streaming assistant bubbles, temporary activity rows for thoughts/reasoning/tool calls, and a Claude Code-inspired conversational workflow.
3. Live AI window for previews, browser surfaces, generated UI, or future agent workspaces.

The visual language should be simple, modern, and Apple-esque: quiet contrast, high spacing discipline, restrained glass/depth, native-feeling controls, and no marketing-style landing page. The first screen is the working interface.

Chat streaming should keep transient agent activity inside the active assistant message bubble. Thought/reasoning parts, tool calls, and tool results should appear as temporary activity rows while the response is being assembled. The final assistant text streams into the same bubble. Backend `done` events terminate the stream internally and should not render as their own chat bubble.

Screen sharing is explicit. The chat surface exposes a `share screen with agent` control and a visible sharing status indicator. When enabled, the desktop shell shows a color-changing ring around the actual desktop display so the user can tell the agent is allowed to view the screen. The backend only registers screenshot and image-analysis tools for chat requests that include screen-sharing consent. The agent should capture temporary screenshots only when visual context is necessary or likely changed.

The sidebar also lets the user choose a skills folder. When selected, that folder is passed to the agent on each chat request so it can search that folder first for reusable skills, prompts, and workflows. If a `skills.md` file exists in the selected folder, the agent should treat it as the canonical skills index and prefer editing that file when adding or updating a skill.

The chat composer also exposes speech-to-text input outside the text entry area. In the current prototype this records raw microphone audio in the renderer, uploads it to the local backend, and transcribes it locally with mlx-whisper before inserting the dictated text into the message draft. The renderer still needs microphone permission in the trusted desktop shell.

## Frontend Architecture

The desktop app uses Electron, Vite, React, and TypeScript.

Electron main process responsibilities:

1. Launch and monitor the local FastAPI backend.
2. Manage local subprocesses where needed.
3. Persist desktop-side app settings.
4. Expose a narrow, secure IPC bridge.
5. Manage app windows and future detachable preview/browser windows.
6. Show a transparent always-on-top screen-sharing ring while desktop viewing is enabled.

Renderer responsibilities:

1. Render the three-pane interface.
2. Stream chat and tool-call events from the backend into a single active assistant message.
3. Provide MCP add/edit/start/stop controls.
4. Render the live AI window as an embedded preview pane in the MVP.
5. Maintain UI state with small local stores.
6. Let the user toggle screen sharing and speech-to-text input.

## Backend Architecture

The backend uses FastAPI as the local API boundary and Google ADK as the agent runtime. FastAPI should expose clean endpoints for health, chat streaming, sessions, MCP registry state, workspace roots, memory inspection, and preview events.

ADK owns model calls, tool invocation, session state, and evaluation workflows. The app uses OpenRouter through ADK LiteLLM. Model identifiers should be configurable through environment variables or app settings.

The chat runtime should call `Runner.run_async(...)`, loop through each ADK event, and translate event content into the frontend stream contract. Function calls become `tool_call` events, function responses become `tool_result` events, `Part.thought` text becomes `thought` events, and normal text parts become `assistant_message` events.

Initial model roles:

1. Primary execution model: configurable OpenRouter model.
2. Scout retrieval model: rule-based or cheap model in early phases.
3. Dreamer consolidation model: deterministic/rule-based stub first, configurable LLM later.

## Storage

SQLite is the default local persistence layer. It stores app settings, chat metadata where needed, MCP configuration, workspace roots, NBAM observations, consolidation state, and indexes. ADK agent sessions use `SqliteSessionService` from `google.adk.sessions.sqlite_session_service`.

ADK sessions and NBAM durable memory are separate systems:

1. ADK sessions track conversation/runtime state.
2. NBAM tracks durable, curated, auditable knowledge.

## MCP Tooling

MCP servers are represented as editable config records with these fields:

1. id
2. name
3. command
4. args
5. env
6. enabled
7. autoStart
8. status
9. toolFilter

The first built-in MCP preset is Playwright:

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": [
        "@playwright/mcp@latest",
        "--browser=chrome",
        "--caps=vision",
        "--shared-browser-context",
        "--timeout-action=10000",
        "--timeout-navigation=90000",
        "--output-dir=data/playwright-output"
      ]
    }
  }
}
```

The backend should expose enabled MCP servers to ADK through `McpToolset` using stdio connection params. The UI should show status and logs, but ADK should own actual MCP tool invocation.

For the current prototype, MCP toolsets are included in the ADK agent only when the corresponding MCP config is both enabled and marked `running` from the sidebar. Playwright starts as an enabled auto-running config so browser tools such as `browser_navigate` are available after backend reloads. The preset uses a shared Playwright browser context without a fixed `--user-data-dir`, allowing the agent to reuse its open browser window during a run without taking a lock on a durable browser profile. ADK stdio MCP connections use a longer timeout than the SDK default because first browser launches can take more than five seconds.

## Custom ADK Tools

All file tools are scoped to user-granted workspace roots. Every path must resolve inside an allowed root before the backend reads or writes.

Required initial tools:

1. `list_directory`: list immediate children with type, size, and ignore filtering.
2. `folder_tree`: bounded recursive tree with max depth and max entries.
3. `read_file_section`: read text files by line range with size and binary checks.
4. `ripgrep_search`: call `rg` with `shell=False`, timeout, max results, and structured match output.
5. `create_file`: create a new file inside an allowed root, failing if it already exists unless overwrite is explicitly requested.
6. `replace_file_section`: apply bounded line-range edits and return a unified diff.
7. `insert_at_line`: insert content at a line and return a unified diff.
8. `get_git_diff`: return a read-only diff for user review.

Additional prototype tools:

1. `capture_desktop_screenshot`: save a current macOS desktop screenshot into an app-managed screenshot directory.
2. `analyze_image`: inspect a local image or screenshot with a vision-capable model using the configured OpenRouter API key.

These tools are request-gated by the screen-sharing flag and should not be registered for ordinary chat turns.

Sensitive edit tools should later be wrapped with ADK confirmation support once the UI confirmation flow exists.

## Guarded Terminal Sessions

The prototype includes persistent terminal sessions for development and inspection workflows, but they are not an unrestricted shell tool.

Rules:

1. Terminal sessions are keyed by user id and chat session id.
2. The agent must explicitly spawn a terminal before running commands in it.
3. Terminal cwd persists across commands until the session is closed.
4. Commands are validated by a command policy before execution.
5. Shell control operators, redirection, pipes, command substitution, and unapproved executables are rejected.
6. Terminal cwd changes must remain within the configured path policy.
7. Output is capped and commands time out.

## Node-Based Agentic Memory

NBAM follows the design in `/Users/derekin/Desktop/agent_memory.md`.

Core rules:

1. Live sessions never mutate durable graph nodes directly.
2. Live sessions append raw observations only.
3. Dreamer consolidation emits structured patch operations.
4. Deterministic validation must pass before durable node writes are applied.
5. Active durable nodes are capped at 300.
6. Deprecated nodes are preserved for audit but excluded from default scout traversal.

Phase 1 NBAM includes:

1. File-backed markdown nodes with structured frontmatter.
2. Append-only observation log in SQLite or JSONL.
3. Consolidation state with last consolidated offset.
4. Compact manifest for scout retrieval.
5. Deterministic validator for schema, links, timestamps, node cap, and status rules.
6. Rule-based dreamer stub that can discard, create, update, deprecate, and link nodes through patch operations.

Current prototype integration status:

1. Chat requests append raw user and assistant observations to the observation log.
2. The agent can inspect memory status and read an existing node directly.
3. The configured dreamer model is `google/gemini-3.1-flash-lite` for future LLM-backed consolidation.
4. Scout retrieval, dreamer consolidation execution, and validator-driven node mutation are not yet wired into the live chat runtime.

## Constraints And Safety Rules

1. Default prototype filesystem access is full local filesystem access when `JARVIS_FULL_FILESYSTEM_ACCESS=true`.
2. Workspace-scoped access remains available by disabling full access and setting `JARVIS_ALLOWED_ROOTS`.
3. File tools must reject path traversal and symlink escapes outside allowed roots when scoped mode is enabled.
4. Search and read tools must enforce output limits.
5. Edit tools must return diffs.
6. Git commits are not allowed in MVP.
7. Shell execution is not exposed as a general agent tool in MVP.
7a. The guarded terminal session tools are allowed because they enforce command policy, cwd policy, timeouts, and output limits rather than exposing arbitrary shell access.
8. MCP server commands are user-configured and must be shown transparently in the UI.
9. Secrets such as `OPENROUTER_API_KEY` must be loaded from environment or local secret storage, not committed.
10. Missing dependencies such as ripgrep must produce clear diagnostics.

## Success Criteria

1. The desktop app starts and shows the three-pane interface.
2. The backend starts locally and exposes a health endpoint.
3. The chat UI can send a prompt to the backend and display streamed assistant text with thoughts, reasoning, and tool-call activity grouped inside the active assistant bubble.
4. The Playwright MCP preset appears in the sidebar and can be started or stopped through backend MCP service endpoints.
5. File exploration tools reject paths outside allowed roots.
6. Ripgrep tool reports a clear missing dependency when `rg` is unavailable.
7. NBAM can append an observation and validate a minimal node patch operation.
8. Project setup commands are documented and reproducible.

## Edge Cases

1. `OPENROUTER_API_KEY` is missing.
2. `rg` is not installed.
3. A user selects a path outside allowed roots.
4. A file is binary or too large to read.
5. An MCP server fails to start or exits early.
6. The backend is already running on the default port.
7. NBAM validation fails after dreamer emits a patch.
8. The live preview receives an unknown or unsupported preview type.
9. An old ADK session contains a failed tool call without a matching tool response.
