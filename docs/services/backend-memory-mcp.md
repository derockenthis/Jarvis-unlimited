# Backend Memory And MCP

## Scope

This document covers the two backend service areas that extend the base chat runtime: NBAM memory and MCP toolsets.

Primary files:

| File | Role |
| --- | --- |
| `apps/backend/app/services/memory_service.py` | Runtime facade for NBAM node and observation storage. |
| `apps/backend/app/memory/node_store.py` | File-backed markdown node storage. |
| `apps/backend/app/memory/observations.py` | SQLite-backed append-only observation log. |
| `apps/backend/app/memory/schemas.py` | Pydantic memory schemas. |
| `apps/backend/app/memory/manifest.py` | Manifest-related memory scaffold. |
| `apps/backend/app/memory/scout.py` | Scout retrieval scaffold. |
| `apps/backend/app/memory/dreamer.py` | Dreamer/consolidation scaffold. |
| `apps/backend/app/memory/validator.py` | Deterministic patch validation scaffold. |
| `apps/backend/app/tools/memory_tools.py` | ADK wrappers for memory status and node reads. |
| `apps/backend/app/services/mcp_service.py` | In-memory MCP registry and ADK toolset cache. |
| `apps/backend/app/mcp/presets.py` | Built-in MCP configs. |
| `apps/backend/app/mcp/adk_toolset.py` | Bridge from `McpToolConfig` to ADK `McpToolset`. |
| `apps/backend/app/routes/mcp.py` | HTTP list/start/stop controls for MCP tools. |

## Memory Service

`MemoryService` is the runtime facade over NBAM primitives.

Constructor dependencies:

1. `Settings.memory_root` for node storage.
2. `Settings.sqlite_path` for the observation log.
3. `Settings.memory_dreamer_model` for status reporting and future consolidation.

Runtime state:

1. `node_store`: `NodeStore(memory_root)`.
2. `observation_log`: `ObservationLog(sqlite_path)`.
3. `_message_indices`: in-memory counter by session id.
4. `memory_promotion_state`: SQLite-backed per-session promotion cursors, including the last promoted ADK event count.

## Observation Logging

`ObservationLog` creates an `observations` table if needed:

| Column | Meaning |
| --- | --- |
| `offset` | Autoincrement ordering key. |
| `id` | Unique observation id. |
| `timestamp` | UTC ISO timestamp. |
| `session_id` | Chat/session key. |
| `message_index` | Message order within the session according to `MemoryService`. |
| `observation` | Raw observation text. |
| `consolidated` | Flag reserved for future dreamer/scout pipeline. |

`MemoryService.append_observation(session_id, text)` initializes storage, appends a row, and increments the in-memory message index for that session.

`MemoryService.promote_session_observations(session_id, event_count=...)` reads unconsolidated observations for that session, asks the ADK-backed dreamer proposer for patch operations, falls back to the rule-based dreamer stub if that call fails or returns invalid JSON, validates accepted patches, writes durable nodes for `create_node` operations, and then marks the source observations consolidated. The service records the latest processed ADK event count per session so the dreamer runs once per true event delta instead of once per cycle bucket.

Current limitation: message indices reset when the backend process restarts because `_message_indices` is in memory.

## Node Store

`NodeStore` stores durable nodes as markdown files under:

```text
{memory_root}/nodes/{node_id}.md
```

It provides:

1. `initialize()` to create the nodes directory.
2. `node_path(node_id)` to resolve a node file path.
3. `write_node(node_id, content)` to write markdown.
4. `read_node(node_id)` to read markdown.
5. `list_node_ids()` to list existing node ids.

Each node document stores structured JSON frontmatter plus markdown body. The frontmatter now carries retrieval and grouping metadata including `weight` (0.0-1.0 importance), `tree` (logical group such as `general` or `project_scope`), and optional `parent_id` for simple hierarchy inside a tree. If a promoted node arrives without `parent_id`, the backend creates a stable tree-root node for that tree and attaches the child automatically.

The live chat runtime still appends raw observations first, but after a completed turn it now runs the deterministic promotion loop through `MemoryService`. That loop is the only live path that writes durable nodes during normal chat.

## Memory Status And Tools

`MemoryService.status()` returns:

1. Memory root path.
2. Node count.
3. Node ids.
4. Observation count.
5. Observation log path.
6. Configured dreamer model.

`MemoryService.read_node(node_id)` returns markdown content or a structured not-found error.

`build_memory_tools(memory_service)` still exists as an ADK-facing inspection wrapper, but it is no longer part of the ordinary root-agent tool surface for chat turns. NBAM promotion runs through the backend runtime after completed turns rather than through model-invoked memory inspection tools.

## NBAM Pipeline Status

The memory package contains the intended pieces for Node-Based Agentic Memory:

1. Schemas for nodes, observations, and patches.
2. Manifest/scout retrieval scaffold.
3. Dreamer consolidation scaffold.
4. Validator scaffold for deterministic checks before durable mutation.

Current live integration is intentionally conservative:

1. User and assistant chat turns append raw observations.
2. After a completed turn, the runtime counts new ADK `events` rows since the last successful promotion for that session. Only when the new-event delta reaches `Settings.memory_promotion_interval` does `MemoryService.promote_session_observations(...)` evaluate unconsolidated observations for that session.
3. The default proposer is an ADK-backed dreamer that is instructed to emit JSON patch operations for a batch of observations.
4. If the ADK dreamer call fails or returns invalid JSON, the rule-based dreamer stub takes over and only promotes explicit memory-style prefixes such as `rule:`, `decision:`, `remember:`, and `task:`.
5. Deterministic validation must pass before a durable node is written.
6. Parent tree-root nodes are created by the backend when needed so dreamer patches do not need filesystem tools or prior durable tree setup.
7. The agent can inspect memory status and read an existing node.
8. Patch application is currently limited to `create_node` and `discard_observation`; richer update and merge operations remain future work.

## MCP Service

`McpService` owns MCP registry state for the backend process.

Internal state:

| Field | Purpose |
| --- | --- |
| `_tools` | Map of `tool_id` to `McpToolConfig`. Seeded with the Playwright preset. |
| `_manually_stopped_tool_ids` | Prevents auto-start tools from immediately restarting after user stop. |
| `_toolsets` | Cached ADK MCP toolset objects by tool id. |
| `_toolset_fingerprints` | Command and args fingerprints used to decide whether a cached toolset can be reused. |

Primary methods:

1. `list_tools()` returns current configs.
2. `ensure_auto_started_tools()` marks enabled auto-start tools running unless manually stopped.
3. `start_tool(...)` marks a known tool running and clears manual stop state.
4. `stop_tool(...)` marks a known tool stopped and records manual stop state.
5. `resolve_running_tools()` creates or reuses ADK toolsets for enabled running configs, calls `toolset.get_tools()`, and closes stale cached toolsets.

MCP start/stop does not directly run the tool. Toolsets are resolved when the next ADK chat runner is built.

## Playwright Preset

The built-in preset is defined in `mcp/presets.py`:

```text
npx @playwright/mcp@latest --browser=chrome --caps=vision --shared-browser-context --timeout-action=10000 --timeout-navigation=90000 --output-dir=data/playwright-output
```

It is enabled, auto-started, and initially running. This makes browser automation tools available to ADK after backend startup unless the user stops the preset from the sidebar.

## ADK MCP Bridge

`build_mcp_toolset(config)` creates an ADK `McpToolset` with stdio connection params.

Important details:

1. It uses `StdioServerParameters(command=config.command, args=config.args)`.
2. It sets a 60-second timeout to handle slow first browser launches.
3. It returns the toolset object, and `McpService` later calls `get_tools()`.

`build_running_mcp_toolsets(...)` and `resolve_running_mcp_tools(...)` are helper functions for config lists, but the live runtime currently uses the caching behavior in `McpService.resolve_running_tools()`.

## MCP Route Contract

`routes/mcp.py` exposes:

1. `GET /api/mcp/tools` for listing configs.
2. `POST /api/mcp/tools/{tool_id}/start` to enable a config for future ADK runs.
3. `POST /api/mcp/tools/{tool_id}/stop` to disable a config for future ADK runs.

Responses use `McpActionResponse` with `tool_id`, `status`, and user-facing `message`.

## Revision Notes

1. Persist MCP config and manual stop state if users need settings to survive backend restarts.
2. Add MCP subprocess health and logs so the UI can distinguish configured, running, failed, and connected states.
3. Persist or recalculate memory message indices after restart if exact per-session ordering matters.
4. Extend patch application beyond `create_node` once merge, deprecation, and link mutation semantics are finalized.