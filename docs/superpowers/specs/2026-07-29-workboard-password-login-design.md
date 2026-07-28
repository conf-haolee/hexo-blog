# Workboard Password Login Design

## Goal

Provide a fast private first release for `work.cvhao.top` without Cloudflare Zero Trust. The Workboard runs on the NAS behind the existing Cloudflare Tunnel and requires one owner-managed password before private data is available.

## Scope

- Add a login page and logout action to the Workboard service.
- Store only a password hash and session secret in NAS container environment variables.
- Protect all HTML, static assets, API endpoints, and document downloads except login, logout, and health checks.
- Keep the existing Cloudflare Access mode available for a later migration.

## Authentication Flow

1. A visitor requests `work.cvhao.top`.
2. If no valid signed session cookie exists, the service redirects HTML requests to `/login`; API requests return `401`.
3. The login form submits the password over HTTPS.
4. The server verifies the password against `WORKBOARD_PASSWORD_HASH`, then creates a 30-day signed session cookie using `WORKBOARD_SESSION_SECRET`.
5. Logout clears the session cookie.

## Security Controls

- Passwords use Werkzeug's password hash verification; plaintext passwords are never stored in code, Git, browser storage, or logs.
- Cookies are `HttpOnly`, `Secure`, and `SameSite=Lax`.
- Login attempts are rate-limited in memory to slow password guessing.
- State-changing requests retain the existing same-origin check and add a CSRF token requirement in password mode.
- `WORKBOARD_AUTH_MODE=cloudflare` continues to trust Cloudflare Access headers; `WORKBOARD_AUTH_MODE=password` activates the new mode.

## Configuration

The NAS Compose project will use:

```text
WORKBOARD_AUTH_MODE=password
WORKBOARD_PASSWORD_HASH=generated_on_nas_before_deploy
WORKBOARD_SESSION_SECRET=generated_on_nas_before_deploy
WORKBOARD_ALLOWED_ORIGINS=https://work.cvhao.top
```

The password hash and session secret are generated directly on the NAS before deployment, then copied only into the NAS Compose environment configuration. They are not committed.

## Verification

- Unauthenticated page access redirects to login.
- Wrong password does not create a session.
- Correct password creates a session and loads projects and TODOs.
- Logout revokes access in the current browser.
- API writes without the CSRF token fail.
- Existing Cloudflare mode remains covered by unit tests.
