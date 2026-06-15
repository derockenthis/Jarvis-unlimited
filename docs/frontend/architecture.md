# Frontend Architecture

## Purpose

The frontend is the Electron renderer for Jarvis Agent Desktop. It is built with React, TypeScript, Vite, Zustand, lucide-react, and a small markdown rendering pipeline for assistant messages. Its job is to render the three-pane working surface, keep UI state local and predictable, and communicate with the FastAPI backend over HTTP.

The renderer does not directly access the filesystem, ADK, MCP subprocesses, or shell commands. Those capabilities stay behind backend APIs or narrow Electron IPC.

## Top-Level Layout

| Path | Responsibility |
| --- | --- |
| `src/renderer/main.tsx` | Mounts React into the DOM. |
| `src/renderer/App.tsx` | Composes the shell and mirrors screen-sharing state into Electron IPC. |
| `src/renderer/components/Sidebar.tsx` | Navigation rail for Provider, MCP Tools, Skills, and local Recent Chats. |
| `src/renderer/components/WorkspacePanel.tsx` | Switches the center pane between chat and selected workspace views. |
| `src/renderer/components/ProviderSettingsView.tsx` | Shows provider/model settings, saved profile loading, autosave, and Ollama model discovery. |
| `src/renderer/components/McpToolsView.tsx` | Shows MCP tool status plus start/stop controls. |
| `src/renderer/components/SkillsView.tsx` | Shows skills folder selection and clearing controls. |
| `src/renderer/components/ChatPane.tsx` | Owns message composition, chat streaming, speech recording, screen-sharing toggle, and chat rendering. |
| `src/renderer/components/LiveWindow.tsx` | Placeholder preview/work surface for future browser, file, UI, or task surfaces. |
| `src/renderer/api/backend.ts` | Typed-ish fetch wrapper for backend HTTP endpoints and SSE parsing. |
| `src/renderer/stores/useAppStore.ts` | Zustand store for backend URL, MCP tools, chat messages, provider settings, preview state, and transient UI flags. |
| `src/renderer/types.ts` | Shared renderer-side types for chat events, MCP tools, messages, activities, and preview items. |
| `src/renderer/styles.css` | Global visual system for shell, sidebar, chat, composer, message activity, and live window. |
| `electron/main.cjs` | Electron main process, main window creation, permissions, IPC handlers, and screen-share overlay windows. |
| `electron/preload.cjs` | Context bridge exposed as `window.jarvisDesktop`. |

## Shell Composition

`App.tsx` renders one root `main.app-shell` containing:

1. `Sidebar` for workspace navigation and local recent chat rows.
2. `WorkspacePanel` for the active center view: chat, Provider, MCP Tools, or Skills.
3. `LiveWindow` for preview/workspace surfaces.

`App.tsx` also fetches the backend URL from Electron through `window.jarvisDesktop.getBackendUrl()` and pushes screen-share activity to Electron through `window.jarvisDesktop.setScreenShareRing(active)`.

## State Model

`useAppStore.ts` is the only renderer store. It contains:

1. Layout: `sidebarCollapsed` and `activeWorkspaceView`.
2. Backend integration: `backendUrl`.
3. MCP state: `mcpTools` plus `setMcpTools` and `setMcpToolStatus`.
4. Chat state: `messages`, `activeAssistantId`, `isStreaming`, and `addChatEvent`.
5. Screen state: `isScreenSharing` and `isScreenViewing`.
6. Skills state: `skillsRootPath`, persisted in `localStorage`.
7. Model provider state: `provider`, `model`, `apiKey`, `baseUrl`, and `speechModel`, persisted in `localStorage`.
8. Preview state: one `PreviewItem` for `LiveWindow`.

The store appends every submitted user turn plus an empty assistant message. The generated assistant id is saved in `activeAssistantId`, so streamed backend events mutate only the current assistant bubble. Assistant messages keep tool activities and streamed thoughts separately so thought events can remain visible after a turn finishes.

## Sidebar

`Sidebar.tsx` is the left rail. It is navigation-only and currently includes:

1. Provider.
2. MCP Tools.
3. Skills.
4. Recent Chats.

Provider, MCP Tools, and Skills update `activeWorkspaceView`, which makes `WorkspacePanel` replace the center chat pane with the selected view. Recent Chats are currently local and derived from recent user messages in the current renderer session; selecting one returns the center pane to chat.

Detailed configuration no longer lives in nested sidebar containers. `ProviderSettingsView`, `McpToolsView`, and `SkillsView` own the detailed controls in the center pane.

## Workspace Views

`WorkspacePanel.tsx` reads `activeWorkspaceView` from the store and renders one center-pane view.

Provider settings allow selecting `OpenRouter`, `OpenAI`, or `Ollama (Local)`. For OpenRouter and OpenAI, users can enter an API key, model name, optional base URL, and speech model. For Ollama, users can enter an Ollama server URL and choose a detected local model.

When Ollama is selected, the provider view calls `fetchOllamaModels(backendUrl, baseUrl || 'http://localhost:11434')`. The backend then probes `/api/tags` and returns discovered model names. If a model is found and the current model is absent or not available, the store selects the first returned model.

Speech model defaults to `mlx-community/whisper-large-v3-turbo` for local transcription via mlx-whisper, or can be set to an OpenRouter model like `openrouter/qwen/qwen3-asr-flash-2026-02-10` for cloud transcription.

MCP controls call:

1. `GET /api/mcp/tools` on mount to populate the list.
2. `POST /api/mcp/tools/{tool_id}/start` to mark a tool running.
3. `POST /api/mcp/tools/{tool_id}/stop` to mark a tool stopped.

Skills folder selection uses Electron IPC through `window.jarvisDesktop.pickSkillsFolder()`. The selected path is stored in `localStorage` and sent on every chat request.

## ChatPane

`ChatPane.tsx` owns the central conversation workflow.

On submit it sends the draft to `streamChat(...)` with:

1. Message text.
2. Static session id and user id.
3. Screen-sharing consent.
4. Selected skills root.
5. Selected provider, model, API key, and base URL.
6. `addChatEvent` callback for streamed backend events.

It also owns speech-to-text recording with `MediaRecorder`. The component records audio, posts it to `POST /api/speech/transcribe` with the configured `speechModel` from the store, and inserts returned transcript text into the draft.

The screen-sharing control toggles `isScreenSharing`. This has two effects:

1. The next chat request includes `screen_share_enabled: true`, which lets the backend attach screenshot and image tools.
2. `App.tsx` tells Electron to show or hide the desktop screen-sharing ring.

## Chat Event Rendering

The renderer consumes server-sent events from `POST /api/chat` through `api/backend.ts`. It parses frames by looking for `data: ...` lines and calls `addChatEvent` with each parsed `ChatEvent`.

`addChatEvent` maps events this way:

| Event type | Store behavior | UI behavior |
| --- | --- | --- |
| `assistant_message` | Appends content to `activeAssistantId`. | Text streams into the active assistant bubble. |
| `thought` | Adds a persistent thought entry to the active assistant message. | Collapsible Agent thoughts panel above the assistant response. |
| `tool_call` | Adds a `ChatActivity`; sets screen viewing for screenshot tool calls. | Tool activity row with tool name/status/detail. |
| `tool_result` | Adds a `ChatActivity`. | Tool result row with status/detail. |
| `error` | Ends active turn and appends an error message. | Separate error bubble. |
| `done` | Clears transient tool activity rows and active assistant id. | Completes the current turn while preserving assistant content and thoughts. |

Assistant message text is rendered in `ChatPane.tsx` through `react-markdown` with `remark-gfm`, so the chat surface can display headings, emphasis, inline code, fenced code blocks, lists, and GitHub-flavored tables.

Before markdown rendering, the component applies a narrow normalization pass for common model output mistakes that would otherwise break display fidelity. The current cleanup handles malformed heading and list spacing, blank lines inside table blocks, and broken bold label patterns such as `**Label: ** ** Value**`.

The CSS in `styles.css` now includes dedicated chat markdown rules for tables, code, blockquotes, headings, and horizontal overflow inside assistant bubbles.

## Backend API Client

`api/backend.ts` centralizes renderer calls:

1. `streamChat(...)` posts to `/api/chat` and parses SSE frames.
2. `transcribeAudio(...)` posts a `FormData` audio blob to `/api/speech/transcribe`.
3. `fetchOllamaModels(...)` calls `/api/models/ollama` with an encoded base URL.
4. `fetchMcpTools(...)` calls `/api/mcp/tools`.
5. `startMcpTool(...)` and `stopMcpTool(...)` call MCP control endpoints.

The renderer treats the backend as the trust boundary for local capabilities. Fetch failures become visible chat errors or silent empty model lists depending on the interaction.

## Electron Boundary

`electron/main.cjs` creates the main window and exposes a small native surface:

1. `backend:get-url` returns the configured backend URL.
2. `screen-share:set-ring-active` shows or hides transparent always-on-top overlay windows across active displays.
3. `skills-folder:pick` opens a native directory picker.
4. Media permissions are granted only to the trusted renderer origin.

The screen-sharing ring is a visual consent indicator, not the screenshot mechanism. Screenshots are captured by backend tools only when the chat request enables screen sharing.

## Styling Direction

`styles.css` defines a quiet desktop app surface: constrained panes, glass-like panels, restrained borders, message bubbles, activity rows, and compact controls. New UI should stay practical and scan-friendly. The first viewport should remain the working application, not a landing page.

## Current Gaps

1. Model provider state is persisted in `localStorage`, including API keys. This is acceptable for prototype speed but should move to secure local storage before production use.
2. Ollama chat currently runs without backend ADK tool declarations so local models can answer normally; provider-specific tool support should be negotiated per model before enabling tools for Ollama.
3. `LiveWindow` is still a placeholder and does not yet receive backend preview events.
4. MCP tool configuration is not editable or durable from the renderer yet; only start/stop status is exposed.