# Workboard Password Login Implementation Plan

> **For agentic workers:** Required workflow: implement each task in order, run the listed verification, and do not touch files outside `workboard/` and this documentation area.

**Goal:** Protect `https://work.cvhao.top` with a single independent password, while retaining the existing Cloudflare Access mode as an optional alternative.

**Architecture:** Flask verifies a password hash stored only in NAS environment variables. Successful login creates a signed, secure session cookie. All Workboard pages, API endpoints, and document downloads require that session, except the login page and health endpoint. Stateful operations require a CSRF token.

**Tech Stack:** Python 3.12, Flask, Werkzeug password hashing, Flask test client, Docker Compose.

## Constraints

- Modify only `workboard/` and this plan document.
- Never commit a plaintext password, password hash, session secret, tunnel token, or NAS/VPS credential.
- Preserve `WORKBOARD_AUTH_MODE=cloudflare` compatibility.
- Keep `/api/health` unauthenticated for Docker health checks.

## Task 1: Implement the Password Authentication Boundary

**Files:**
- Modify: `workboard/server.py`
- Create: `workboard/tests/__init__.py`
- Create: `workboard/tests/test_password_auth.py`

1. Add failing tests for unauthenticated page/API access, login success/failure, logout, CSRF enforcement, and retained Cloudflare-header access mode.
2. Add `password` mode configuration using `WORKBOARD_PASSWORD_HASH` and `WORKBOARD_SESSION_SECRET`; reject requests safely when either is missing.
3. Configure a 30-day signed cookie with `HttpOnly`, `Secure`, and `SameSite=Lax` attributes.
4. Add `GET` and `POST` `/login`, `POST` `/logout`, and authenticated `GET /api/session` endpoints.
5. Generate and validate session-bound CSRF tokens. Require the token for every state-changing API request and logout.
6. Rate-limit repeated failed password submissions by source address in a short rolling window.
7. Protect normal HTML/static content and existing API/document routes in `before_request`; redirect browser page requests to login and return JSON `401` for APIs.
8. Run `python -m unittest discover -s workboard/tests -v` and fix failures.

## Task 2: Add the Login and Logout User Interface

**Files:**
- Create: `workboard/static/login.html`
- Modify: `workboard/static/index.html`
- Modify: `workboard/static/script.js`
- Modify: `workboard/static/style.css`

1. Build a minimal Chinese login page with a password input, generic failure message, and no secret-bearing browser code.
2. Add a visible logout control to the private dashboard.
3. Fetch the authenticated session during startup and attach the CSRF token to all mutation requests.
4. Make logout send its CSRF token, clear the server session, and return to the login page.
5. Add lightweight source assertions for login route/DOM hooks and run the full unit test command again.

## Task 3: Update NAS Deployment Configuration and Documentation

**Files:**
- Modify: `workboard/docker-compose.yml`
- Modify: `workboard/Dockerfile` only if a safe default needs adjustment
- Modify: `workboard/README.md`

1. Set the Compose deployment template to `WORKBOARD_AUTH_MODE=password`.
2. Load password hash and session secret exclusively from an untracked NAS `.env` file/environment.
3. Restrict allowed browser origin to `https://work.cvhao.top`.
4. Document NAS commands/UI values for generating a password hash and session secret, rebuilding the Workboard container, and verifying health/login/logout.
5. Run `docker compose config` with temporary local values when Docker is available; otherwise validate YAML structure and document that Docker must be validated on NAS.

## Task 4: Final Verification and Handoff

**Files:**
- Verify: all changed `workboard/` files

1. Run Python compilation and unit tests.
2. Inspect the diff to confirm no credential or unrelated blog change was included.
3. Commit only the Workboard authentication implementation and this plan.
4. Give the user exact NAS deployment instructions: update files, create the NAS-only `.env`, rebuild `workboard`, then test `https://work.cvhao.top`.
5. Do not claim the live site is protected until the NAS container is rebuilt with the new image and environment variables.
