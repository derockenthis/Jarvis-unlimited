# Services Documentation

This folder contains deeper, file-oriented documentation for the major frontend and backend service boundaries.

## Index

| Document | Scope |
| --- | --- |
| [backend-agent-runtime.md](backend-agent-runtime.md) | Chat runtime, root agent, ADK session handling, provider/model selection, and SSE event translation. |
| [backend-api-services.md](backend-api-services.md) | FastAPI routes, dependency injection, endpoint-facing services, health, speech, workspace, and model discovery. |
| [backend-tools-security.md](backend-tools-security.md) | Filesystem tools, edit tools, ripgrep, guarded terminal sessions, path policy, and command policy. |
| [backend-memory-mcp.md](backend-memory-mcp.md) | NBAM storage primitives, observation logging, memory tools, MCP presets, and ADK MCP toolset resolution. |
| [frontend-renderer-services.md](frontend-renderer-services.md) | Renderer store, backend API client, sidebar provider controls, chat pane, live window, and Electron IPC boundary. |

These docs are implementation-oriented. The product-level source of truth remains [../DESIGN_SPEC.md](../DESIGN_SPEC.md).