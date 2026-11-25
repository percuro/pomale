# Changelog

All notable changes to this project are documented here. Versions follow [Semantic Versioning](https://semver.org/); until 1.0 a minor version may contain breaking changes, which are always listed under "Upgrade notes".

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
