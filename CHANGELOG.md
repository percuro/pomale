# Changelog

All notable changes to this project are documented here. Versions follow [Semantic Versioning](https://semver.org/); until 1.0 a minor version may contain breaking changes, which are always listed under "Upgrade notes".

## 0.6.0 – goals, pauses, groups, history

### Features

- Three goal types per habit, each versioned with an effective date like the weekdays, so past weeks keep their numbers:
  - **on chosen days** (as before),
  - **n× a week, any day** ("run 3× a week"): today shows "1 of 3 this week"; once the week is done the habit moves to "done this week" and can still be checked off as extra,
  - **an amount per day** ("8 glasses of water"): − and + on today, a tap on the row sets the target, days below the target are "partly done".
- **Pauses** for holidays or illness, for all habits or one, also entered afterwards: paused days are not due and do not lower the quota. A weekly target shrinks in weeks with paused days and in the first week.
- **Optional note** per habit and day, from its own button – never part of checking off. Shown in week and history, included in the CSV.
- **Groups and colours:** named groups split today and week into sections; a colour from a fixed palette marks each habit (always next to its name, never instead of it).
- **Drag to sort** on the habits page (touch, mouse, keyboard with screen-reader announcements), plus the arrow buttons.
- **History page:** quota for the last 4, 12, 26 and 52 weeks, a 12-week trend with the numbers as a table, and a month calendar whose cells name their state. No streaks.
- **Shortcut and quantity goals:** each run adds 1, or `amount` (1–1000); the answer reads "Water: 5 of 8 glasses".
- API: `goal_type`, `target`, `unit`, `color` and `group_id` on habits; `value` on check-ins; `/v1/groups`, `/v1/pauses`, `PUT /v1/habits/order`, `PUT /v1/habits/{id}/days/{day}/note` and `GET /v1/history`.

### Upgrade notes

- Migration 0005 runs automatically. Existing habits become "on chosen days" goals; nothing changes for them.
- **New `state` values** `paused` and `partial` in `/v1/days` and check-in answers. Clients should treat unknown states like "not planned".
- `PUT /v1/habits/{id}/days/{day}` takes `done` **or** `value`; sending both, or a value for a non-quantity habit, is a 422.
- Every day in `/v1/days` has the new fields `goal_type`, `target`, `paused`, `value` and `note`; the answer has `groups`, and each habit has `week` for weekly goals.
- The shortcut's `result` can now also be `counted` (quantity goals).
- **CSV export:** new columns `value`, `target` and `note` at the end, so existing evaluations keep working. Paused and partly done days are listed with their state.
- The web app drops cached day lists from 0.5 once (they are reloaded); unsent changes stay queued and are sent as before.
- New frontend dependency: `@dnd-kit/core`, `@dnd-kit/sortable`, `@dnd-kit/utilities`.

## 0.5.0 – single sign-on, audit log

### Features

- Optional sign-in through your own OpenID Connect provider (Authelia, Authentik, Pocket ID, Keycloak, …), configured with `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_SCOPES` and `OIDC_LABEL`. See [docs/oidc.md](docs/oidc.md).
  - Accounts get there through an invitation ("Continue with …"), by linking an existing account on the account page, in the first-run setup, or automatically with `OIDC_AUTO_CREATE=on`.
  - `PASSWORD_LOGIN=off` turns passwords off entirely.
  - Accounts without a password confirm sensitive changes by signing in at the provider again, and can set a password later.
  - Admins see how each account signs in and can remove a provider link; reset links are now "recovery links" that set a password or link a provider account.
- Audit log on the admin page: logins and failed logins, rate-limit blocks, account creation and deletion, password changes, roles, (de)activation, invitations, provider links and shortcut keys, also from the command line. Kept for `AUDIT_RETENTION_DAYS` (default 180).
- `GET /api/v1/meta` also reports `password_login` and whether single sign-on is available; `/auth/me` reports `has_password` and the provider link.

### Fixes

- Logging out in the header now returns to the login page; before, the page stayed on the signed-in view with "not logged in" errors.

### Security

- OIDC: authorization code flow with PKCE (S256); only asymmetrically signed ID tokens; issuer, audience, `azp`, expiry, nonce and subject are checked; accounts are linked by issuer and subject, never by e-mail address. Each sign-in is bound to the browser that started it and works once within 10 minutes.
- Linking a provider account needs the password; removing the last way to sign in is refused.
- The audit log stores IP addresses only shortened (IPv4 /24, IPv6 /48) and only for failed logins and rate-limit blocks. A block is logged once, not for every refused request.

### Upgrade notes

- Migration 0004 runs automatically. Nothing to configure: without `OIDC_ISSUER` everything works as before.
- New dependency: `joserfc` (JWT verification).
- API: `DELETE /api/v1/account` and `POST /api/v1/account/password` take the password as before; accounts without a password leave it out and may get `403 auth.reauth_required`.

## 0.4.0 – accounts, invitations, German and English

### Features

- Several accounts per instance. Everyone has their own habits, time zone and language; nobody sees other accounts' data.
- Roles: admins invite people with a one-time link (copy it or use the share sheet), see the list of accounts (username, display name, role, status, created, last active – never habits or check-ins), change roles, deactivate, reactivate and delete accounts, and create password-reset links. Admins never see or set passwords.
- Optional open registration with `REGISTRATION=open` (default: invitations only).
- Account page: display name, time zone, language, password change, list of logged-in devices with log-out, CSV export (moved here from the habits page), deleting the own account.
- Time zone per account: "today" is computed in the account's time zone, the shortcut uses the time zone of the habit's owner. Accounts without their own setting use `DEFAULT_TIMEZONE`; the app offers to switch when the device is in a different zone.
- English and German interface: the account's setting, else the choice on the login page, else the browser language, else English. Dates and weekday names follow the language; weeks always start on Monday.
- CSV column names and the shortcut's text follow the account's language. The shortcut response has a new language-independent field `result` (`done` / `already_done`).
- `GET /api/v1/meta` with version, registration mode and whether setup is needed.
- CLI: `create_user --role admin|user` and `python -m app.cli.set_role <username> admin|user` as an emergency exit.

### Security

- Invitation and reset tokens live in the URL fragment (never in server logs or Referer headers) and are stored as hashes; a link works once, atomically. Wrong tokens are rate-limited per IP address.
- Deactivating an account logs it out everywhere at once and stops its shortcut keys.
- The last active admin cannot be demoted, deactivated or deleted.
- Password changes log out all other devices; password confirmations share the login rate limit.
- Sessions record a coarse device name from the User-Agent for the device list; no IP addresses are stored.
- Open registration is impossible before the first-run setup, so a fresh instance cannot be taken over that way.
- A test calls every route that takes an ID with another account's IDs and fails when a new route is missing from it.

### Upgrade notes

- **Existing accounts become admins.** Demote accounts on the admin page if needed.
- API errors now look like `{"detail": "<English message>", "code": "<stable code>"}`; `detail` is no longer German. Clients should match on `code`. The 409 sync conflict carries the server state in a top-level `server` field (was `detail.server`). Deactivated accounts get 401 instead of 403.
- `DEFAULT_TIMEZONE` now only applies to accounts without their own time zone. Changing a time zone never moves check-ins; it only changes which calendar day is "today".
- New usernames have 3–32 characters from `a–z`, `0–9`, `.`, `_` and `-`; existing names stay valid.
- Web app paths are English: `/today`, `/week`, `/habits` (the old German paths redirect).
- The iOS shortcut keeps working unchanged. Its message is now in the owner's language (or the phone's, else English); compare `result`, not the text, in automations.
- Dependency updates: FastAPI 0.165, SQLAlchemy 2.1, Pydantic 2.14, Alembic 1.20, Uvicorn 0.54, React Router 7.18.

## 0.3.0 – first public release

### Features

- Today view: check off a habit with one tap, undo next to it, rows never jump
- Week view: habits × days with keyboard navigation and a "4 of 5 due days" quota
- Habits: daily or on chosen weekdays, schedule changes with an effective date, sorting, archiving
- Unplanned days can be checked off as extra without affecting the quota
- Offline: installable web app, local queue of changes, pending marks, conflict dialog instead of silent overwrites; entries keep their original date
- iOS shortcut widget: revocable key for one habit, the server determines "today"
- CSV export (semicolon, UTF-8 with BOM)
- First-run setup in the browser with a one-time token from the server log
- One container image (amd64, arm64) serving API and frontend; SQLite on a volume; plain SQL dump and restore commands; health endpoint with version

### Security

- Server-side sessions with HttpOnly cookies, login rate limit, CSRF protection (header plus origin check) on by default
- Content Security Policy and further security headers; HSTS for https deployments
- Shortcut keys stored as hashes only, limited to one habit and to "done today"
