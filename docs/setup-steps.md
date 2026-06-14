# Setup Steps

Date: 2026-06-08

## What I did

1. Checked the machine for existing tooling and confirmed `node`, `npm`, `brew`, and `uv` were missing from the PATH.
2. Installed `nvm` in the user home directory and used it to install Node.js `20.20.2`, which provided `npm 10.8.2`.
3. Installed `uv` with `python3 -m pip install --user uv` and used the user-local executable from `~/Library/Python/3.14/bin/uv`.
4. Created the backend virtual environment and installed dependencies with:

   ```bash
   cd apps/backend
   uv sync --all-groups
   ```

5. Installed the workspace JavaScript dependencies with:

   ```bash
   npm install
   ```

6. Repaired Electron by rerunning its installer so the macOS app bundle was downloaded into `node_modules/electron/dist`.
7. Started the backend with `uvicorn app.main:app --reload --host 127.0.0.1 --port 8765`.
8. Started the desktop app with `npm run desktop:dev`.
9. Verified the local services were reachable:
   - Backend health endpoint returned `200`.
   - Vite served `http://127.0.0.1:5173/`.
   - Electron processes were running.

## Notes

- The backend `.venv` was created at `apps/backend/.venv`.
- Homebrew was not used because the account does not have sudo access on this machine.
- The backend startup log shows LiteLLM warnings about missing `botocore`; the app still started successfully.