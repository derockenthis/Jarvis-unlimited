# Frontend Renderer Services

## Scope

This document breaks down the renderer-side services and integration files.

Primary files:

| File | Role |
| --- | --- |
| `apps/desktop/src/renderer/stores/useAppStore.ts` | Zustand state store and chat event reducer. |
| `apps/desktop/src/renderer/api/backend.ts` | HTTP/SSE API client for FastAPI. |
| `apps/desktop/src/renderer/components/Sidebar.tsx` | Navigation rail for Provider, MCP Tools, Skills, and local Recent Chats. |
| `apps/desktop/src/renderer/components/WorkspacePanel.tsx` | Center-pane view switcher. |
| `apps/desktop/src/renderer/components/ProviderSettingsView.tsx` | Provider settings, Ollama model detection, saved profile loading, and autosave. |
| `apps/desktop/src/renderer/components/McpToolsView.tsx` | MCP tool list plus start/stop controls. |
| `apps/desktop/src/renderer/components/SkillsView.tsx` | Skills folder selection and clearing. |
| `apps/desktop/src/renderer/components/ChatPane.tsx` | Chat submit, streaming event handling, screen share toggle, and speech recording. |
| `apps/desktop/src/renderer/components/LiveWindow.tsx` | Current preview placeholder. |
| `apps/desktop/src/renderer/types.ts` | Shared renderer-side contracts. |
| `apps/desktop/electron/main.cjs` | Electron native window, permission, and IPC implementation. |
| `apps/desktop/electron/preload.cjs` | Safe bridge exposed to the renderer. |

## Store Service

`useAppStore.ts` is the central renderer service. It stores UI state and provides mutation methods.

State groups:

| Group | Fields |
| --- | --- |
| Layout | `sidebarCollapsed`, `activeWorkspaceView`. |
| Backend | `backendUrl`. |
| MCP | `mcpTools`. |
| Chat | `messages`, `activeAssistantId`, `isStreaming`. |
| Screen sharing | `isScreenSharing`, `isScreenViewing`. |
| Skills | `skillsRootPath`. |
| Provider settings | `provider`, `model`, `apiKey`, `baseUrl`. |
| Preview | `preview`. |

Persistence:

1. `skillsRootPath` is stored as `jarvis.skillsRootPath` in `localStorage`.
2. Provider settings are stored as `jarvis.provider`, `jarvis.model`, `jarvis.apiKey`, and `jarvis.baseUrl`.

Security note: API keys are currently stored in `localStorage`. This is easy for a prototype but should be moved to secure local storage or an encrypted backend settings store before production.

## Chat Event Reducer

`addUserMessage(content)` creates:

1. A user message with the submitted content.
2. A new empty assistant message.
3. An `activeAssistantId` pointing to the new assistant message.

`addChatEvent(event)` then routes stream events to the active assistant message:

| Event | Store action |
| --- | --- |
| `assistant_message` | Appends streamed text to the active assistant message. |
| `thought` | Adds a persistent thought entry to the active assistant message. |
| `tool_call` | Adds an activity row and toggles `isScreenViewing` when the screenshot tool starts. |
| `tool_result` | Adds an activity row with status/detail. |
| `error` | Clears the active turn and appends an error message. |
| `done` | Clears transient tool activity and closes the active turn without removing stored thoughts. |

The active assistant id prevents later stream events from mutating older assistant bubbles.

## Backend API Client

`api/backend.ts` provides fetch wrappers.

`streamChat(...)`:

1. Posts to `/api/chat`.
2. Sends message, session id, user id, screen-sharing flag, skills root, provider, model, API key, and base URL.
3. Reads `response.body` as a stream.
4. Splits frames on double newlines.
5. Parses the first `data: ...` line in each frame.
6. Calls the supplied event callback with a `ChatEvent`.

`transcribeAudio(...)`:

1. Builds `FormData` with an `audio` blob.
2. Picks `ogg` or `webm` filename extension based on MIME type.
3. Posts to `/api/speech/transcribe`.
4. Returns text or throws a detailed error.

`fetchOllamaModels(...)`:

1. Calls `/api/models/ollama?base_url={encodedBaseUrl}`.
2. Returns the `models` array.
3. Returns an empty list for non-OK responses.

MCP helpers list, start, and stop MCP tools through `/api/mcp` routes.

## Sidebar And Workspace Behavior

`Sidebar.tsx` is navigation-only. It updates `activeWorkspaceView` for Provider, MCP Tools, and Skills, and derives local Recent Chats from the current renderer messages. Selecting a recent chat row returns the center pane to chat.

`WorkspacePanel.tsx` reads `activeWorkspaceView` and renders `ChatPane`, `ProviderSettingsView`, `McpToolsView`, or `SkillsView` in the center column.

`ProviderSettingsView.tsx` owns provider settings behavior.

Provider settings:

1. Reads and writes `provider`, `model`, `apiKey`, and `baseUrl` through the store.
2. Shows OpenRouter, OpenAI, and Ollama provider options.
3. Shows API key, model name, and optional base URL fields for OpenRouter/OpenAI.
4. Shows Ollama URL and model dropdown for Ollama.
5. Calls `fetchOllamaModels(...)` when provider is Ollama.
6. Selects the first detected Ollama model if the current model is missing or unavailable.

MCP controls:

1. Calls `fetchMcpTools(...)` on mount.
2. Renders each tool with status.
3. Calls `startMcpTool(...)` or `stopMcpTool(...)` on user action.
4. Writes tool status into the store.
5. Adds tool result or error events into chat activity.

Skills folder:

1. Calls `window.jarvisDesktop.pickSkillsFolder()`.
2. Stores the selected path in the store and `localStorage`.
3. Sends the path with future chat requests.
4. Allows clearing the selected path.

Revision note: provider settings currently use inline styles. Moving those rules into `styles.css` will make the sidebar easier to maintain.

## ChatPane Service Behavior

`ChatPane.tsx` owns the active conversation UI when `activeWorkspaceView` is `chat`.

Submission flow:

1. Trim the draft.
2. Stop any active microphone recording.
3. Add the user and assistant placeholder messages.
4. Clear the draft and set streaming true.
5. Await `streamChat(...)` with current store settings.
6. Convert failures into `error` chat events.
7. Set streaming false when the stream exits.

Speech-to-text flow:

1. Detect `navigator.mediaDevices.getUserMedia` and `MediaRecorder` support.
2. Request microphone access.
3. Record supported audio MIME type candidates.
4. Stop tracks after recording.
5. Upload the blob through `transcribeAudio(...)`.
6. Append returned transcript text to the draft.

Screen-sharing flow:

1. Toggle `isScreenSharing` from the composer toolbar.
2. Show a status pill in the chat header.
3. Include screen-sharing consent in chat requests.
4. Let `App.tsx` mirror state to Electron's screen-share ring.

Rendering flow:

1. `messages` are rendered as role-specific message articles.
2. Persisted thought events render in a collapsible Agent thoughts panel above assistant content.
3. Tool activities render separately above message content while streaming.
4. Assistant text is rendered through the markdown pipeline with GFM support and local malformed-markdown normalization.
5. The composer remains at the bottom of the chat pane.

## Live Window

`LiveWindow.tsx` currently reads one `PreviewItem` from the store and renders a placeholder preview stage.

Supported preview kinds in `types.ts` are:

1. `component`.
2. `browser`.
3. `file`.
4. `empty`.

The current UI does not yet have backend preview events or a mounted browser/file/component surface. Future work should add a typed preview event contract rather than overloading chat messages.

## Electron IPC Boundary

The renderer talks to Electron through `window.jarvisDesktop` from the preload bridge.

Current native capabilities:

| Capability | Main process handler | Renderer use |
| --- | --- | --- |
| App/backend info | `app:get-info`, `backend:get-url` | `App.tsx` reads backend URL. |
| Screen ring | `screen-share:set-ring-active` | `App.tsx` mirrors sharing/viewing state. |
| Skills folder picker | `skills-folder:pick` | `SkillsView.tsx` lets the user choose a folder. |

`electron/main.cjs` also grants media permissions only for the trusted renderer origin and opens external links outside the app.

## Revision Notes

1. Move API keys out of `localStorage` before production.
2. Add a typed preview event system for `LiveWindow`.
3. Add durable MCP config editing once backend persistence exists.
4. Consider a provider-aware status indicator so users can see whether OpenRouter, OpenAI, or Ollama is ready before submitting a chat.