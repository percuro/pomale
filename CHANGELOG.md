# Changelog

All notable changes to this project are documented here. Versions follow [Semantic Versioning](https://semver.org/); until 1.0 a minor version may contain breaking changes, which are always listed under "Upgrade notes".

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
