# Backend Architecture

## Overview

The backend is a FastAPI service that exposes local APIs for health, chat streaming, MCP registry actions, workspace access, and future memory/preview endpoints. Google ADK owns the agent runtime, model calls, tool invocation, and session state.

## Request Flow

1. `main.py` creates the FastAPI app and registers route modules.
2. `routes/` modules stay thin and delegate behavior to services.
3. `services/` modules provide endpoint-facing orchestration.
4. `dependencies.py` wires cached settings, path policy, chat runtime, and services.
5. `runtime/adk_runner.py` drives the live Google ADK Runner.

## Chat Runtime

`ChatRuntime` builds the ADK runtime lazily so health checks and non-chat endpoints can run even before a model call is needed. It uses:

1. `build_root_agent(...)` from `agent/root_agent.py` for the Jarvis root agent and OpenRouter-backed LiteLLM model.
2. `SqliteSessionService` for ADK session state.
3. `build_agent_tools(policy)` from `tools/agent_tools.py` to register policy-bound filesystem/search/edit tools.
4. Session-bound terminal tools from `tools/terminal_tools.py` backed by `SessionTerminalService`.
5. Screen-sharing-gated desktop screenshot and image-analysis tools from `tools/vision_tools.py` backed by `DesktopVisionService`.
6. Memory status and node-read tools from `tools/memory_tools.py` backed by `MemoryService`.
7. Resolved MCP tools from running MCP configs via `mcp/adk_toolset.py`.
8. `runner.run_async(...)` to loop through ADK events.
9. Event translation into the frontend stream contract: `thought`, `tool_call`, `tool_result`, `assistant_message`, `done`, and `error`.

## Tooling

Custom tools are split into testable core functions and ADK-facing wrappers:

| Layer | Purpose |
| --- | --- |
| `tools/file_explorer.py` | Directory listing and bounded folder tree traversal. |
| `tools/search_tools.py` | Bounded file reads and ripgrep search with clear diagnostics. |
| `tools/edit_tools.py` | Guarded file creation, line replacement, and insertion with unified diffs. |
| `tools/agent_tools.py` | ADK-compatible wrappers that close over `PathPolicy` and return dictionaries. |
| `tools/terminal_tools.py` | Session-bound ADK wrappers for persistent terminal spawn/run/read/close actions. |
| `tools/vision_tools.py` | ADK wrappers for desktop screenshot capture and local image analysis. |
| `tools/memory_tools.py` | ADK wrappers for memory status inspection and durable node reads. |
| `security/path_policy.py` | Full-access or workspace-scoped path resolution. |
| `security/command_policy.py` | Guardrail for allowed terminal commands and shell syntax rejection. |
| `services/session_terminal_service.py` | Persistent per-session terminal state, cwd management, command execution, and output capture. |
| `services/desktop_vision_service.py` | macOS screenshot capture and OpenRouter-backed vision analysis for local images. |
| `services/memory_service.py` | Basic NBAM runtime wiring for observation logging and node store inspection. |

## MCP

`mcp/presets.py` defines the Playwright preset as an auto-running shared-context Chrome MCP server with vision capability. `services/mcp_service.py` manages in-memory start/stop/status state and respects manual stops even when a preset is auto-startable. Running MCP configs are resolved into concrete ADK browser tools through `mcp/adk_toolset.py` when the chat runtime builds the agent. `StdioConnectionParams` uses a 60-second timeout so first browser launches and navigations do not fail at ADK's default five-second client timeout. The preset avoids fixed `--user-data-dir` profiles so the agent can reuse its open Playwright browser context without taking a durable profile lock. The next layer should persist MCP configs and add deeper subprocess health reporting.

## Memory

The NBAM modules under `memory/` are separate from ADK sessions. `MemoryService` now initializes the node store, appends raw user and assistant observations during chat, and exposes status and node-read tools to the agent. The dreamer model setting is `google/gemini-3.1-flash-lite` for future LLM-backed consolidation. Durable node writes, scout retrieval, and dreamer-driven consolidation are still future work and must go through patch operations plus deterministic validation before becoming active knowledge.

## Session Recovery

ADK sessions can become invalid if a previous run left provider history with an unmatched tool-call id. `ChatRuntime` detects missing-tool-response and tool-not-found session errors, resets the ADK session once through `SqliteSessionService.delete_session(...)`, recreates it, and retries the current request. This keeps old failed MCP attempts from poisoning later chat turns.

## Validation

Backend validation currently includes health, MCP preset exposure, chat stream formatting through dependency override, path policy behavior, tool behavior, and NBAM schema/validator tests.