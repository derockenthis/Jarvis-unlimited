# Jarvis Agent Desktop

Jarvis Agent Desktop is a local-first Electron desktop AI environment with a React chat UI, a FastAPI backend, Google ADK for agent orchestration, OpenRouter for models, MCP tool management, and Node-Based Agentic Memory scaffolding.

## Structure

```text
apps/desktop   Electron + React + TypeScript UI
apps/backend   FastAPI + Google ADK runtime and tools
docs/          Product docs, implementation status, architecture notes, glossary
```

## Requirements

- Node.js 20+
- npm 10+
- Python 3.12+
- uv
- ripgrep (`rg`) for agent search tools
- OpenRouter API key for live model calls

## Setup

```bash
cp .env.example .env
npm install
cd apps/backend
uv sync
```

Set `OPENROUTER_API_KEY` in `.env` or your shell before using live LLM calls.

## Development

Run the backend:

```bash
npm run backend:dev
```

Run the desktop app in another terminal:

```bash
npm run desktop:dev
```

Run focused validation:

```bash
npm run desktop:typecheck
npm run backend:test
```

## Current Status

The app has a working three-pane UI, a FastAPI backend, live Google ADK Runner chat streaming through OpenRouter, SQLite-backed ADK sessions, policy-bound filesystem/search/edit tools, MCP preset controls, and NBAM Phase 1 scaffolding.

Project docs live in [docs/DESIGN_SPEC.md](docs/DESIGN_SPEC.md), [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md), [docs/frontend/architecture.md](docs/frontend/architecture.md), [docs/backend/architecture.md](docs/backend/architecture.md), and [docs/ubiquitous_terminology.md](docs/ubiquitous_terminology.md).

# Jarvis-unlimited
