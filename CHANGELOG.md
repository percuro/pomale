# Changelog

All notable changes to this project are documented here. Versions follow [Semantic Versioning](https://semver.org/); until 1.0 a minor version may contain breaking changes, which are always listed under "Upgrade notes".

## 0.11.0-rc.2 – beta (release candidate)

- Fixed: on iPhone and iPad, date and time fields ("Starts on", pauses, reminder times) stuck out of the form on the right and showed their value centred. They now have the width of the other fields and start on the left; tapping still opens the picker.
- Everything else as in 0.11.0-rc.1 below. No migration, no new settings.

## 0.11.0-rc.1 – beta (release candidate)

No new features: this release makes pomale sturdier to run and to update before the API and the settings are frozen in 1.0.

### Updates

- **Tested updates:** every change is now tested by starting the 0.3.0 image and the previous release, adding data, and starting the new image on the same volume. Accounts, habits, check-ins, archived habits and shortcut keys must survive unchanged, and the updated instance must log in, check off with an old shortcut key and back up and restore. You can update from any release since 0.3.0 straight to the newest one; see [Updates](docs/self-hosting.md#updates).
- Release images are only built after all checks have passed for the tagged commit.

### Accessibility

- After a change of page the focus moves to the start of the content and screen readers announce the new page, as after a page load. Before, the focus stayed on the link in the navigation.
- A missing or used invitation link now has a heading.
- The automatic WCAG 2.2 AA checks now also cover dialogs, forms and results that appear after a click, the setup, invitation and registration pages and the English interface. See [Accessibility](docs/accessibility.md).

### Performance

- The app start loads about a fifth less code (452 instead of 574 kB, 140 instead of 170 kB compressed): history, habits, account and administration load the first time they are opened. Offline use is unchanged; the app keeps all pages on the device.
- The JSON export no longer runs one database query per habit.

### Fixes

- `GET /api/v1/today` (Siri, Home Assistant) listed a habit archived the same day as still open.
- Five wrong setup tokens from anyone blocked the first-run setup for everyone for 15 minutes. They are now counted per IP address.
- A failed daily backup could leave a half-written file in the backup folder; an unreadable backup folder stopped the daily backups until the next restart.
- Stopping the container while a backup or a round of reminders was running no longer cuts it off; pomale waits up to 10 seconds for it.

### Upgrade notes

- **Settings are checked more strictly.** A switch must be `true`/`false`, `on`/`off`, `yes`/`no` or `1`/`0`, a number a whole number above 0, and `COOKIE_SAMESITE` one of `lax`, `strict` or `none`. Anything else now stops the start with a message naming the variable; before, an unknown switch value silently meant "off" (for example `BACKUP_ENABLED=ja` turned backups off) and a wrong number meant the default. Empty variables still mean the default. Check `docker compose logs app` after the update.
- **Request size:** a request body may be at most 1 MB (imports 5 MB as before) and must come with a `Content-Length`. Browsers, iOS shortcuts, curl and reverse proxies send one; a body sent in chunks without a length is refused with 411.
- No migration, no new settings.

## 0.10.0 – keys, export, backups

### Features

- **API keys** ("Account" → "API keys"): for scripts, iOS shortcuts and home automation. A key can **read** (days, habits, history, exports) and/or **check off** (done, amounts, notes), for all habits or only some, optionally expiring after 30, 90 or 365 days. Everything else – the account, sessions, devices, keys, changing habits, administration – is never reachable with a key; new endpoints stay closed until they are allowed explicitly. See [docs/api.md](docs/api.md), with a Home Assistant example.
- **What is still open today:** `GET /api/v1/today` lists the open habits with their progress and one sentence in the account's language ("Still open: Read, Water (3 of 8 glasses)"), e.g. for Siri ([docs/iphone.md](docs/iphone.md)) or a Home Assistant sensor.
- **JSON export and import** ("Account" → "Your data"): everything of an account in one file – habits with plans, reminder times, check-ins and notes, groups, pauses, time zone, language and day end. The file imports into an account without habits, groups and pauses, all or nothing, e.g. to move to another instance. Admins can do the same with `app.cli.export_account` and `app.cli.import_account`.
- **Built-in daily backups:** at 03:00 (`DEFAULT_TIMEZONE`) a compressed SQL dump goes to `/data/backups` and is kept for 14 days; a new or long-stopped instance backs up a minute after starting. "Administration" → "Backups" shows the state and backs up on demand. `python -m app.cli.backup` backs up now, `restore_sql --from <file>` restores a backup file. See [Backup and restore](docs/self-hosting.md#backup-and-restore).
- **API description** at `/api/openapi.json` for Postman, Bruno, Insomnia or code generators, with the operations a key can use and their scopes.

### Fixes

- Five wrong shortcut keys from anywhere blocked every shortcut of the instance for 15 minutes. Wrong keys are now counted per IP address (20 in 15 minutes).
- `/api/docs` and `/api/redoc` were served by accident and stayed empty under the Content-Security-Policy. They are gone; the description is `/api/openapi.json`.
- Dependabot alert for `minimatch` (build tools only): `glob` is pinned to a fixed version.

### Upgrade notes

- 0.10.0 also brings everything from 0.9.0-rc.1 below (a day end after midnight, migration 0007); 0.9 was not released on its own.
- **Migration 0008** runs automatically. Shortcut keys become API keys that may check off their one habit; **shortcuts set up on phones keep working** with their `ht_…` keys. New keys start with `pm_`. Going back to 0.9 keeps the shortcut keys but drops other API keys.
- **Backups are on by default** and write to `/data/backups`, next to the database on the same volume (usually a few MB). Set `BACKUP_ENABLED=false` if you back up another way. New settings: `BACKUP_ENABLED`, `BACKUP_TIME`, `BACKUP_KEEP_DAYS`, `BACKUP_DIR`, `API_DOCS`.
- Daily backups run inside the app process, like reminders: still exactly one instance with one worker.
- A request with `Authorization: Bearer …` and without the session cookie is authenticated as an API key everywhere (before: only the shortcut endpoint) and needs no CSRF header.
- The shortcut endpoint `PUT /v1/habits/{id}/days/today` now also accepts a logged-in session. An invalid key answers `401` with `code` `token.invalid` (was `shortcut.invalid_token`); a key for another habit `403` with `token.habit_not_allowed` (was `shortcut.wrong_habit`).
- Audit log: keys are logged as `token.created` and `token.revoked`; older entries keep `shortcut.key_*`. New: `account.imported`, `backup.created`.
- New endpoints: `GET/POST/DELETE /v1/account/tokens`, `GET /v1/today`, `GET /v1/export.json`, `POST /v1/import`, `GET/POST /v1/admin/backups`; `/v1/meta` has `api_docs`.

## 0.9.0-rc.1 – night owls (release candidate, released with 0.10.0)

### Features

- **Your day can end after midnight:** "Account" → "My day ends at", from midnight (default, as before) up to 06:00 in full hours. Until then the night still belongs to the day before: at 00:30 with a day end of 01:00, "Today", the week, the history and the iOS shortcut all still use yesterday's date. Between midnight and the day end, "Today" says until when your day runs.
- **Reminders** follow the day end: a reminder time before it belongs to the day that is ending, and its Done button checks off that day. The habit form marks such times with "counts for the day before".
- Check-ins never move: like a change of time zone, changing the day end only changes which day is "today".

### Fixes

- A reminder due shortly before the end of the day (e.g. 23:55) that could not be sent because of a restart is now caught up just after the day end, for the day it was meant for, within the same 15 minutes as other missed reminders. Before, it was dropped.
- After a change of time zone, the web app moved "today" only on its next check (up to 30 seconds); now at once.

### Upgrade notes

- Migration 0007 runs automatically and adds `users.day_end_hour` (0 for every account, so nothing changes until someone picks a later day end). No new settings.
- API: `GET /v1/auth/me` has the new field `day_end_hour` (0–6), and `PATCH /v1/account` accepts it. `today` in `me` and `/v1/days` already takes it into account.

## 0.8.0 – a new look

### Features

- **New look "morning paper"**: moss green on a warm paper, a light top bar, capsule buttons, a rounded heading face on Apple devices and a new, light app icon. People who have the app on their home screen see the new icon after adding it again.
- **The ring** shows the state of a day everywhere in the same way: empty when open, partly filled with the amount inside, filled with a check when done. "Today" shows the share that is done as a ring next to the date; the week and the history calendar use the same rings instead of boxes and characters.
- The **navigation** has icons and marks the active view with a pill. It sits at the bottom on phones and tablets and moves into the top bar from 840 px (before: 640 px). The name of the app stays visible on a phone.
- **Account** is an icon in the top bar. **Logging out** and, for administrators, the way to the **administration** moved to the account page: the bar is for places, not actions.
- Drawn icons replace characters such as ✎, ↶ and ⠿, which looked different on every system.
- Edges of fields and buttons and the focus ring are clearly stronger (at least 3 : 1); dialogs open as a sheet from the bottom on a phone.
- On iPhone and iPad the text follows the system text size. The window title names the page ("Week · pomale").
- Styles are split into five layers (`frontend/src/styles/`), with one set of colour roles and components shared with fahrma, see the [design language](docs/design-language.md). A test checks 40 colour pairs against the WCAG contrast minimum in both schemes; the end-to-end tests scan the main pages for WCAG 2.2 AA violations and for sideways scrolling at 320 px.

### Fixes

- The button of a quantity goal on "Today" had a name for screen readers that did not contain its visible text.
- Icons carry a version in their address (`/icon.svg?v=…`), so that browsers fetch a changed icon instead of showing the cached one for a week. Bookmarks pick up the new icon the next time the page is opened; some browsers only do so after the bookmark is added again.

### Upgrade notes

- No migration and no new settings. Logging out moved from the top bar to the account page. The roadmap moves by one version: API tokens, export/import and backups are planned for 0.9.

## 0.7.0 – reminders

### Features

- **Reminders via Web Push:** up to three times per habit, in the account's time zone. A notification comes only if the habit is still open then: done, paused, not planned and reached weekly goals stay quiet; quantity goals show "3 of 8 glasses". Habits due in the same minute come as one notification.
- **Done button** in the notification for a single habit on Android and desktop: checks it off without opening the app, through the same rules as the offline queue (queued when offline). iPhone and iPad open the app on a tap.
- Works on iPhone and iPad with iOS/iPadOS 16.4 or later in the home-screen app, and in current browsers on Android and desktop. See [docs/reminders.md](docs/reminders.md).
- **Account page → Reminders:** turn reminders on or off per device, send a test, see and remove all devices. Logging out or ending a session removes that device; an expired login keeps it.
- Messages are end-to-end encrypted (RFC 8291); push services never see habit names. Implemented in pomale itself on `cryptography`, `joserfc` and `httpx`, checked against the RFC's test vector.
- A missed reminder (server restart) is caught up for 15 minutes, never twice; clock changes are handled.
- API: `reminders` on habits (`["07:30", "20:00"]`), `/v1/push/config`, `/v1/push/subscriptions` (list, register, remove, test).

### Upgrade notes

- Migration 0006 runs automatically and adds three tables. On the first start pomale creates its Web Push key pair and stores it in the database (log line "VAPID key created"); backups include it.
- **New environment variables:** `PUSH_ENABLED` (default `true`), `PUSH_CONTACT` (default `PUBLIC_URL`; must be `mailto:` or `https://`), `PUSH_ALLOWED_HOSTS`. Nothing has to be set.
- The server now makes **outgoing HTTPS connections** to the push services of Google, Apple, Mozilla and Microsoft, and only to those (extendable with `PUSH_ALLOWED_HOSTS`). A firewall that blocks them stops reminders, nothing else.
- Reminders run inside the app process: still exactly one instance with one worker.
- The service worker is now written by hand (`src/sw.ts`, vite-plugin-pwa `injectManifest`) instead of generated; it caches the same files and updates itself on the next visit.
- `HabitRead` has the new field `reminders`; `HabitCreate` and `PATCH /v1/habits/{id}` accept it (`PATCH` replaces the list).
- New backend dependencies, now direct: `cryptography`, `httpx` (httpx moved from the dev requirements). New frontend dev dependencies: `workbox-core`, `workbox-precaching`, `workbox-routing`.

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
