# Copilot Instructions

- [x] Verify that the copilot-instructions.md file in the .github directory is created.
- [x] Clarify Project Requirements
- [x] Scaffold the Project
- [x] Customize the Project
- [x] Install Required Extensions
- [x] Compile the Project
- [x] Create and Run Task
- [x] Launch the Project
- [x] Ensure Documentation is Complete

## Project Notes

This workspace is a local-first Electron + React + TypeScript desktop app with a FastAPI backend using Google ADK. The canonical requirements live in `docs/DESIGN_SPEC.md`.

No VS Code extensions were required by the selected scaffold. Launch is documented through npm scripts and VS Code tasks; no long-running dev server is left running by default.

Follow these rules when changing code:

- Keep filesystem tools scoped to user-granted workspace roots.
- Do not add unrestricted shell execution as an agent tool.
- Keep ADK session storage separate from NBAM durable memory.
- Do not commit secrets or default API keys.
- Prefer small, typed interfaces between Electron, the renderer, and FastAPI.
- Treat `docs/DESIGN_SPEC.md` as the source of truth for product behavior.
