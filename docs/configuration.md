# Configuration

All settings are environment variables (for Docker Compose: the `.env` file next to `compose.yaml`). Only `PUBLIC_URL` is required.

| Variable | Default | Description |
|---|---|---|
| `PUBLIC_URL` | – (required) | Address users open, e.g. `https://habits.example.org`. Must not contain a path. It is the only origin allowed to make changes (CSRF protection), it decides whether cookies are `Secure`, and it appears in the setup message. |
| `DEFAULT_TIMEZONE` | `UTC` | IANA time zone that defines "today" for accounts without their own time zone, e.g. `Europe/Berlin` or `America/New_York`. Each account can choose its own on the account page. The server clock (usually UTC in containers) is never used for this. `TRACKER_TZ` is accepted as a deprecated alias. |
| `REGISTRATION` | `invite` | `invite`: new accounts only through an admin's invitation link. `open`: anyone who can reach the instance may register (role user, at most 5 registrations per IP address and hour, never before the first-run setup). |
| `INVITE_EXPIRY_DAYS` | `7` | How long an invitation link is valid. Recovery (password-reset) links are always valid for 24 hours. |
| `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_SCOPES`, `OIDC_LABEL`, `OIDC_AUTO_CREATE` | – | Sign-in through your own identity provider (OpenID Connect). Off unless `OIDC_ISSUER` is set. See [Single sign-on](oidc.md). |
| `PASSWORD_LOGIN` | `on` | `off`: no passwords; login, invitations and setup only through the OIDC provider. Requires `OIDC_ISSUER`. |
| `AUDIT_RETENTION_DAYS` | `180` | How long the audit log (admin page → Log) keeps its entries. |
| `DATABASE_URL` | `sqlite:////data/habits.db` | SQLite database file. Keep it on the `/data` volume. Other databases are not supported. |
| `SESSION_IDLE_MINUTES` | `43200` (30 days) | A login expires after this much inactivity. Long on purpose: the home-screen web app on iOS has its own cookie storage, so frequent logins would get in the way of quick check-ins. |
| `SESSION_ABSOLUTE_HOURS` | `2160` (90 days) | Maximum lifetime of a login. |
| `COOKIE_SECURE` | on for `https://` `PUBLIC_URL` | Override only for special setups. |
| `COOKIE_SAMESITE` | `lax` | `lax`, `strict` or `none`. |
| `CSRF_PROTECTION` | `true` | Only disable for local experiments. |
| `CORS_ORIGINS` | – | Additional origins allowed to make changes, comma-separated. Rarely needed. |
| `FORWARDED_ALLOW_IPS` | `*` | Proxies whose `X-Forwarded-For`/`-Proto` headers are trusted. `*` is fine when the container port is only reachable through your reverse proxy (as in the provided `compose.yaml`). If the port is exposed, set it to your proxy's address. The login rate limit relies on the client address. |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `FRONTEND_DIST` | `/app/frontend` in the image | Directory with the built frontend. Unset: API only (development with Vite). |

## Limits

- Run exactly **one** instance with **one** worker process. State such as the first-run setup token and the rate limits lives in memory, and SQLite is not meant for several writers across containers.
- **Rate limits** are kept per process in memory and reset by a restart. Within 15 minutes: 5 failed logins or password confirmations per account and 20 per IP address; 5 wrong invitation or recovery links per IP address; 5 wrong setup tokens and 5 wrong shortcut keys in total; 30 single-sign-on starts and failed callbacks per IP address. Registrations: 5 per IP address and hour. They rely on the real client address, see `FORWARDED_ALLOW_IPS`.
- The app must be served at the root of its own (sub)domain; serving under a path like `/habits` is not supported.
