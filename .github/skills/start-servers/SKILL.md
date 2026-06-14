---
name: start-servers
description: "Use when you need to start the Jarvis backend and desktop dev servers for debugging, verify they are up, or just start the app stack."
---

# Start Servers

Use this skill when you need to bring up the local Jarvis development stack for debugging or a normal start.

## Goal

Start the backend and desktop servers in the correct order, make sure the required environment is available, and verify the app stack is responding.

## Workflow

1. Make sure the local Node and Python toolchain is available in `PATH`.
2. Start the backend dev server.
3. Start the desktop dev app.
4. Verify the backend health endpoint responds.
5. Verify the desktop dev server is reachable.
6. If a server is already running, reuse it instead of starting a duplicate.

## Checks

- Backend should respond on `http://127.0.0.1:8765/health`.
- Desktop dev app should be available on the local Vite port.
- If either server fails to start, inspect the last terminal output and retry with the correct workspace task.

## Commands And Tasks

- Prefer the existing VS Code tasks when available.
- Backend task: `Backend: Dev Server`
- Desktop task: `Desktop: Dev App`

## Notes

- Use this skill for the normal start flow and for debugging startup issues.
- Keep changes minimal: do not install dependencies or modify source code unless the startup failure requires it.