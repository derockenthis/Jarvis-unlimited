# ADK Refactor Progress

## Purpose

This note tracks the backend ADK refactor as the code moves from a desktop-specific runtime shape toward a production-ready ADK layout.

## Completed Changes

1. Moved the canonical agent definition into `app/agent/agent.py`.
2. Split prompt assembly into `app/agent/prompt.py`.
3. Added `app/agent/tools/` as the ADK-facing tool composition namespace.
4. Added `app/agent/provider_config.py` for request-scoped provider validation and model resolution.
5. Added `get_agent_async()` and a default ADK loader path for future smoke runs and eval wiring.
6. Split event translation into `app/agent/event_translation.py`.
7. Updated backend architecture and terminology docs to reflect the canonical `app/agent` ownership model.

## Current Implementation Slice

The next refactor step finishes the internal migration to the canonical agent package:

1. Remove active imports that still depend on `app/runtime/adk_runner.py`.
2. Move MCP tool composition behind `app/agent/tools/` so the runner composes all ADK-facing tools from one package.
3. Replace remaining provider environment mutation with direct LiteLlm runtime arguments when the installed ADK/LiteLLM surface supports it.
4. Re-run the backend suite after each slice and keep the compatibility layer only if something external still requires it.

## In Progress Changes

1. Runtime wiring is moving to direct `app/agent/runner.py` imports instead of routing internal code through `app/runtime/adk_runner.py`.
2. MCP tool composition is being localized under `app/agent/tools/mcp.py` so the runner builds every ADK-facing tool group from the same package.
3. OpenRouter, OpenAI, and Ollama request execution is being switched from process-global environment mutation to direct `LiteLlm(...)` runtime kwargs.

## Completed In This Step

1. `app/dependencies.py`, `app/services/chat_service.py`, and backend tests now import `AgentStreamRunner` directly.
2. `app/runtime/adk_runner.py` remains only as a compatibility shim and is no longer used by internal backend code.
3. MCP composition now runs through `app/agent/tools/mcp.py`.
4. `ProviderRuntimeConfig` now produces direct LiteLlm runtime kwargs for OpenRouter, OpenAI, and Ollama instead of mutating provider-specific process environment variables for normal chat execution.
5. Added regression coverage for provider kwargs generation and kept the existing runtime and MCP behavior checks passing.

## Verification

1. `npm run backend:test` passed after the final refactor slice.
2. Current backend test count: `29 passed`.
3. Final grep check confirms `app/runtime/adk_runner.py` is only referenced by itself.

## Done Criteria For This Step

This step is complete when:

1. The backend imports `AgentStreamRunner` directly instead of routing through the runtime shim.
2. MCP tool composition is agent-local.
3. Provider runtime config no longer depends on mutating process-global environment variables for normal request execution.
4. `npm run backend:test` passes.