# Implementation Status

## Completed

- Created the Electron + React + TypeScript desktop scaffold.
- Created the FastAPI backend scaffold with Google ADK integration points.
- Added OpenRouter and Google AI environment configuration support.
- Added the three-pane UI: collapsible MCP sidebar, central chat, and live AI window.
- Added the Playwright MCP preset.
- Added initial custom filesystem/search/edit tool modules.
- Added NBAM Phase 1 memory schemas, observation log, manifest, scout, dreamer stub, node store, and validator.
- Added backend tests for health, MCP preset exposure, path policy, search behavior, and memory validation.
- Added VS Code tasks and setup documentation.
- Split FastAPI handlers into thin route modules and service modules.
- Connected the chat UI to backend streaming events.
- Added visible timeline rows for agent thoughts, tool calls, tool results, assistant messages, completion, and errors.
- Added MCP start/stop/status service endpoints and sidebar controls.
- Enabled explicit full filesystem access for the local prototype.
- Replaced scaffolded chat responses with live Google ADK Runner event translation.
- Added SQLite-backed ADK sessions with `SqliteSessionService`.
- Registered custom filesystem/search/edit tools with the ADK root agent through policy-bound wrappers.
- Integrated running MCP tool configs into the ADK runtime and verified Playwright MCP browser tools are invoked through the live agent.
- Updated the Playwright MCP preset to an auto-running shared Chrome context with vision capability, no fixed user-data-dir, and a longer ADK stdio timeout so the agent can reuse its open browser window without shared-profile lock errors.
- Added guarded persistent terminal sessions with session-bound ADK tools for spawn, run, read, and close.
- Added desktop screenshot capture and local image-analysis tools so the agent can capture the macOS desktop and inspect saved images.
- Added a `share screen with agent` control, a visible sharing status indicator, and a color-changing desktop ring around the actual desktop display; screen capture tools are only attached to the agent when sharing is enabled.
- Added speech-to-text input in the chat composer using local microphone recording plus backend transcription through an OpenRouter ASR model.
- Added a selectable skills folder in the left sidebar and threaded that folder into chat requests so the agent can search it first and treat `skills.md` inside it as the canonical skills index.
- Improved the root agent prompt for local repository inspection, grounded tool use, and safe file edits.
- Wired basic NBAM runtime storage by appending chat observations to the observation log and exposing memory status and node-read tools.
- Configured the NBAM dream agent model as `google/gemini-3.1-flash-lite` through the dreamer model setting.
- Changed the chat UI so thoughts, reasoning, tool calls, and tool results render as activity inside the active assistant bubble instead of separate permanent event bubbles.
- Removed the visible completion bubble from the chat UI while keeping backend `done` events as an internal stream terminator.
- Fixed chat turn ownership so each prompt creates its own assistant bubble and transient activity rows clear after completion.
- Added one-shot ADK session recovery for stale tool-call history so older failed MCP runs do not keep breaking later chat turns.
- Validated `http://127.0.0.1:5173/` in the browser with a real chat submission that rendered live tool calls inside the assistant bubble and completed with a grounded assistant response.
- Validated the live UI by enabling screen sharing, confirming the ring indicator, and searching Google for `flying pigs` through Playwright MCP browser tools.

## In Progress

- Replace stubbed MCP lifecycle status with real subprocess management.
- Add durable MCP configuration storage.
- Add UI controls to review and constrain full filesystem access.
- Expand NBAM beyond basic observation logging and node inspection into real scout/dreamer consolidation.
- Persist screen-sharing preference and add richer UI around captured screenshots.
- Consider an alternate transcription provider or local Whisper-style fallback if OpenRouter ASR quality is insufficient.

## Next

1. Add durable MCP config storage and real MCP subprocess lifecycle management.
2. Add `get_git_diff` as a read-only review tool.
3. Add UI controls to review and constrain full filesystem access.
4. Expand memory retrieval and consolidation so NodeStore is used for live durable recall, not just status and direct reads.
5. Add MCP lifecycle health reporting and durable MCP config storage.
6. Add Playwright/browser checks for MCP start/stop, screen sharing, and streaming regression coverage.
