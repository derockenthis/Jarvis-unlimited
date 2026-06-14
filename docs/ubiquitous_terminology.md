# Ubiquitous Terminology

| Term | Meaning in this codebase | Primary location |
| --- | --- | --- |
| Jarvis Agent Desktop | The local-first desktop AI operating environment. | `README.md`, `docs/DESIGN_SPEC.md` |
| Renderer | The React UI running inside Electron. | `apps/desktop/src/renderer` |
| Chat Pane | Central UI region for user prompts, assistant responses, and streaming activity. | `apps/desktop/src/renderer/components/ChatPane.tsx` |
| Live AI Window | Right-side preview/work surface for future browser, UI, file, and task views. | `apps/desktop/src/renderer/components/LiveWindow.tsx` |
| MCP Sidebar | Left-side UI for MCP tools, workspace access, settings, and future navigation. | `apps/desktop/src/renderer/components/Sidebar.tsx` |
| Chat Event | Backend stream payload sent over SSE from `/api/chat`. | `apps/backend/app/schemas.py`, `apps/desktop/src/renderer/types.ts` |
| Assistant Bubble | A chat message that groups transient thoughts, reasoning, tool calls, tool results, and final assistant text. | `apps/desktop/src/renderer/stores/useAppStore.ts` |
| Activity Row | A temporary row inside an assistant bubble for `thought`, `tool_call`, or `tool_result` events. | `apps/desktop/src/renderer/components/ChatPane.tsx` |
| Done Event | Backend stream terminator used internally by the client; it is not rendered as a chat bubble. | `apps/backend/app/runtime/adk_runner.py`, `apps/desktop/src/renderer/stores/useAppStore.ts` |
| Active Assistant Turn | The currently streaming assistant message id that owns all incoming activity and text for one user prompt. | `apps/desktop/src/renderer/stores/useAppStore.ts` |
| ADK Runner | Google ADK runtime object that executes the agent and emits events. | `apps/backend/app/agent/runner.py` |
| Root Agent | The Jarvis ADK agent definition, model, instruction, and registered tools. | `apps/backend/app/agent/agent.py` |
| LiteLLM Model | ADK model adapter used to call OpenRouter, OpenAI, and Ollama-compatible models. | `apps/backend/app/agent/agent.py`, `apps/backend/app/agent/provider_config.py` |
| OpenRouter | Model provider configured through environment variables and LiteLLM. | `apps/backend/app/config.py` |
| ADK Session | Conversation/runtime state stored by ADK separately from durable memory. | `apps/backend/app/agent/runner.py` |
| `SqliteSessionService` | ADK SQLite session store used by the live chat runtime. | `apps/backend/app/agent/runner.py` |
| Path Policy | Access guard that resolves paths under allowed roots or full local access in prototype mode. | `apps/backend/app/security/path_policy.py` |
| Agent Tool Wrapper | ADK-facing callable that closes over `PathPolicy` and exposes only model-facing parameters. | `apps/backend/app/agent/tools`, `apps/backend/app/tools/agent_tools.py` |
| Core Tool | Testable filesystem/search/edit function that receives an explicit `PathPolicy`. | `apps/backend/app/tools` |
| Tool Result | Structured result object with `status`, `data`, `error`, and `diff`. | `apps/backend/app/tools/models.py` |
| MCP Tool | User-visible Model Context Protocol server configuration and status record. | `apps/backend/app/schemas.py`, `apps/backend/app/services/mcp_service.py` |
| Running MCP Tools | Concrete ADK tools resolved from MCP configs currently marked `running` and attached to the root agent for that chat request. | `apps/backend/app/mcp/adk_toolset.py`, `apps/backend/app/agent/runner.py` |
| Playwright Preset | Built-in MCP server preset for browser automation. | `apps/backend/app/mcp/presets.py` |
| Screen Sharing | User-controlled mode that lets the agent attach desktop screenshot and image-analysis tools to a chat request. | `apps/desktop/src/renderer/components/ChatPane.tsx`, `apps/backend/app/agent/runner.py` |
| Screen-Sharing Ring | Color-changing visible indicator shown around the desktop display while screen sharing/viewing is active. | `apps/desktop/electron/main.cjs`, `apps/desktop/src/renderer/App.tsx` |
| Speech To Text | Composer-side dictation mode that records a microphone clip, transcribes it on the backend, and inserts the text into the current chat draft. | `apps/desktop/src/renderer/components/ChatPane.tsx`, `apps/backend/app/routes/transcription.py` |
| Desktop Vision Service | Backend service that captures macOS screenshots and analyzes local images through a vision model. | `apps/backend/app/services/desktop_vision_service.py` |
| Session Terminal Service | Backend service that maintains persistent cwd-aware terminal sessions per user and chat session. | `apps/backend/app/services/session_terminal_service.py` |
| Command Policy | Backend validation layer that restricts terminal commands and rejects shell operators or disallowed executables. | `apps/backend/app/security/command_policy.py` |
| NBAM | Node-Based Agentic Memory, the durable curated memory system. | `apps/backend/app/memory` |
| Scout | NBAM retrieval component for selecting relevant durable knowledge. | `apps/backend/app/memory/scout.py` |
| Dreamer | NBAM consolidation component that emits patch operations. | `apps/backend/app/memory/dreamer.py` |
| Dream Agent Model | OpenRouter/LiteLLM model configured for future NBAM dreamer consolidation; currently `google/gemini-3.1-flash-lite`. | `apps/backend/app/config.py`, `apps/backend/app/memory/dreamer.py` |
| Observation Log | Append-only record of raw memory observations from live sessions. | `apps/backend/app/memory/observations.py` |
| Manifest | Compact index for durable memory nodes. | `apps/backend/app/memory/manifest.py` |
| Validator | Deterministic guard for NBAM schema, node cap, links, and status rules. | `apps/backend/app/memory/validator.py` |