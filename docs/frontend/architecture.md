# Frontend Architecture

## Overview

The frontend is the Electron renderer for Jarvis Agent Desktop. It is built with React, TypeScript, Vite, Zustand, and lucide-react, and renders the three-pane desktop experience: MCP sidebar, central chat, and live AI window.

## Runtime Shape

1. `main.tsx` mounts the React app.
2. `App.tsx` composes the shell layout.
3. `components/Sidebar.tsx` renders MCP tool controls and workspace access summaries.
4. `components/ChatPane.tsx` submits prompts and renders grouped streaming chat bubbles.
5. `components/LiveWindow.tsx` owns the preview/work surface placeholder.
6. `api/backend.ts` is the renderer API client for FastAPI endpoints.
7. `stores/useAppStore.ts` owns small UI state: MCP tools, backend URL, chat messages, preview state, and streaming status.
8. `types.ts` defines the renderer-side contracts shared across components and the API client.
9. `electron/main.cjs` owns the native transparent screen-sharing ring window and spans it across connected displays when sharing is active.

## Chat Streaming

The renderer consumes Server-Sent Event frames from `POST /api/chat`. Backend event types map into UI state as follows:

| Backend event | Frontend behavior |
| --- | --- |
| `thought` | Adds a thought/reasoning activity row to the active assistant bubble. |
| `tool_call` | Adds a running tool activity row to the active assistant bubble. |
| `tool_result` | Adds a completed tool activity row with status/detail to the active assistant bubble. |
| `assistant_message` | Appends text to the same active assistant bubble. |
| `done` | Clears temporary activity rows for the active assistant turn, marks streaming complete, and does not render a bubble. |
| `error` | Renders a separate error bubble. |

This keeps intermittent reasoning and tool activity visually temporary while the final assistant answer completes in the same message bubble.

The renderer now tracks an explicit active assistant message id for each submitted user turn. This prevents later events from mutating an older assistant bubble when multiple turns are present in the chat history.

## Screen Sharing

`ChatPane.tsx` exposes a `share screen with agent` button and a header status pill. When enabled, chat requests include `screen_share_enabled: true`, allowing the backend to attach screenshot and image-analysis tools for that turn. `App.tsx` mirrors screen-sharing state into the Electron preload bridge so the main process can show a transparent always-on-top ring around the desktop screen itself.

## Speech To Text

`ChatPane.tsx` also exposes a microphone button outside the text entry row. It requests microphone access, records a short audio clip with `MediaRecorder`, uploads the clip to the backend, and appends the returned transcription to the current draft. The backend uses an OpenRouter ASR model for transcription. Electron still grants media permission only for the trusted local renderer origin.

## Styling

`styles.css` defines the full renderer visual system: quiet glass panels, restrained borders, message bubbles, grouped activity rows, composer, sidebar cards, and live preview surface. The UI should remain a working app surface, not a marketing page.

## Integration Boundaries

The renderer talks to the backend over HTTP only. It does not directly invoke filesystem tools, ADK APIs, MCP subprocesses, or shell commands. Future Electron IPC should remain narrow and typed.

The only current Electron IPC beyond app metadata/backend URL is the boolean screen-ring toggle. Screenshot capture still happens through the backend's gated ADK tools, not directly in the renderer, and speech-to-text is handled by backend transcription after the renderer records a local microphone clip.