# Backend Agent Runtime

## Scope

This document covers the backend files that turn a chat request into a Google ADK run and stream the result back to the renderer.

Primary files:

| File | Role |
| --- | --- |
| `apps/backend/app/routes/chat.py` | HTTP entry point for chat streaming and Ollama model discovery. |
| `apps/backend/app/services/chat_service.py` | Thin service wrapper over `ChatRuntime`. |
| `apps/backend/app/runtime/adk_runner.py` | Builds the ADK runner, attaches tools, runs the model, handles recovery, and translates events. |
| `apps/backend/app/agent/root_agent.py` | Builds the ADK `Agent`, chooses the LiteLLM model string, injects skills context, and defines the instruction. |
| `apps/backend/app/schemas.py` | Defines `ChatRequest`, `ChatEvent`, and related payload schemas. |
| `apps/backend/app/config.py` | Provides model, storage, and filesystem settings. |

## Chat Request Contract

`ChatRequest` currently includes:

| Field | Purpose |
| --- | --- |
| `message` | User prompt. Must be non-empty. |
| `session_id` | ADK/NBAM session key, defaulting to `default` or `desktop-session` from the renderer. |
| `user_id` | Local user key, defaulting to `local-user`. |
| `screen_share_enabled` | Enables screenshot and image-analysis tools for this run. |
| `skills_root` | Optional user-selected skills folder. |
| `provider` | Optional model provider such as `openrouter`, `openai`, or `ollama`. |
| `model` | Optional model id/name for the selected provider. |
| `api_key` | Optional request-level API key from the sidebar. |
| `base_url` | Optional provider base URL, also used by Ollama discovery. |

The renderer sends these fields through `streamChat(...)` in `apps/desktop/src/renderer/api/backend.ts`.

## Runtime Build Flow

`ChatRuntime._build_runner(...)` creates a fresh ADK `Runner` for each chat request:

1. Lazily initializes `SqliteSessionService` for ADK sessions.
2. Asks `McpService.resolve_running_tools()` for concrete MCP tools from running configs.
3. Creates policy-bound filesystem, search, and edit tools with `build_agent_tools(...)`.
4. Selects a request-scoped Playwright MCP subset with `select_mcp_tools(...)`, keeping browser tools compact unless the request clearly needs a broader bundle.
5. Adds vision tools only when `screen_share_enabled` is true.
6. Calls `build_root_agent(...)` with the assembled tools plus provider/model/key/base URL settings.
7. Returns a `Runner` bound to app name `jarvis-desktop` and the SQLite session service.

The runner itself is short-lived; ADK session state persists through the SQLite session service.

## Root Agent

`build_root_agent(...)` imports ADK locally so non-chat endpoints can run even if ADK is not exercised. It constructs:

1. A `LiteLlm` model instance.
2. The Jarvis root instruction.
3. A tool list supplied by the runtime.
4. Optional skills folder context.

The prompt tells the agent to:

1. Use filesystem/search tools before guessing.
2. Use screen tools only when available.
3. Use browser MCP tools by their actual names.
4. Use browser MCP tools by their actual names or the compact browser composite when available.
5. Use small safe file edits and absolute paths.

## Model Selection

Default model selection comes from `Settings.openrouter_model`, exposed as `Settings.openrouter_litellm_model`.

Request-level provider mapping in `build_root_agent(...)` works like this:

| Provider | LiteLLM model result |
| --- | --- |
| `openrouter` | `openrouter/{model}` unless the model already has that prefix. |
| `openai` | `openai/{model}` unless the model already has that prefix. |
| `ollama` | `ollama/{model}` unless the model already has that prefix. |
| other | Uses the provided model name as-is. |

Environment variables are set for OpenRouter, OpenAI, and Ollama base configuration before the agent is created.

`ChatRuntime.stream_chat(...)` validates the selected provider before building the runner. OpenRouter accepts either the request API key or `OPENROUTER_API_KEY`, OpenAI requires a request API key, and Ollama requires no API key.

Ollama currently runs in conversational mode without ADK tool declarations. Direct LiteLLM calls to local Ollama models can reply correctly, but ADK function declarations can cause local models to emit malformed partial JSON such as `{\"` instead of natural language. Tool support should be enabled for Ollama only after model-specific capability negotiation or a separate toggle.

## ADK Session Handling

`_ensure_session_service()` creates `SqliteSessionService` lazily and stores it on the runtime. `_ensure_session(...)` creates a session if ADK has not seen that `user_id` and `session_id` combination before.

`_reset_session(...)` deletes and recreates a session when the runtime sees known recoverable errors:

1. Missing tool results for a previous tool call id.
2. Tool history referencing a tool that is no longer available.

On recovery, the runtime emits a `thought` event explaining that it is resetting stale session tool history, retries once, and then completes normally or returns the retry error.

## Event Translation

`_translate_event(...)` maps ADK events to frontend stream events:

| ADK data | Chat event |
| --- | --- |
| `event.get_function_calls()` | `tool_call`, with JSON args in `payload.detail` when possible. |
| `event.get_function_responses()` | `tool_result`, with status, error, diff, content text, or JSON data summary. |
| `content.parts` where `part.thought` is true | `thought`. |
| `content.parts` regular text | `assistant_message`, after channel marker cleanup. |

The route wraps each `ChatEvent` as an SSE frame:

```text
data: {json}

```

The frontend expects exactly this format.

## Memory Coupling

The runtime appends raw observations through `MemoryService`:

1. Before the ADK run: `user[{user_id}]: {message}`.
2. After assistant chunks stream: `assistant[{user_id}]: {combined assistant text}`.

These observations are still the raw inputs to NBAM, but after a completed turn the runtime now reads the ADK `events` table in SQLite and compares the current event count for that session against the last recorded promotion cursor. When at least `Settings.memory_promotion_interval` new event rows have appeared since the last successful promotion, the runtime asks `MemoryService` to consolidate unconsolidated observations for that session. This makes dreamer promotion a true delta-based workflow instead of a coarse cycle bucket.

The current loop first asks an ADK-backed dreamer proposer for JSON patch operations, then falls back to the deterministic stub if the model call fails or returns unusable output. Durable writes still only happen after validation passes, and the live patch application path remains limited to `create_node` plus `discard_observation`. When a promoted node omits `parent_id`, `MemoryService` now creates a stable tree-root parent node such as `general-root` or `project-scope-root` before writing the child node.

## Revision Notes

Add model-specific Ollama tool capability detection before enabling ADK tools for local models. The current behavior prioritizes reliable local chat responses over tool access when `provider` is `ollama`.