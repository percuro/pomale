# Security policy

## Reporting a vulnerability

Please report vulnerabilities **privately** via GitHub: on the repository page, open the **Security** tab and choose **Report a vulnerability**. Do not open a public issue.

Include what you found, how to reproduce it, and the version (`GET /api/health` shows it). You will get an answer within a week. Fixes are released as soon as possible and credited in the changelog unless you prefer otherwise.

## Supported versions

Only the latest release receives security fixes. Updating is a `docker compose pull && docker compose up -d` (see [docs/self-hosting.md](docs/self-hosting.md)).

## Scope notes

- The app is designed to run behind a TLS reverse proxy, with the container port bound to localhost.
- Rate limits and the first-run setup token are kept in memory; run a single instance (see [docs/configuration.md](docs/configuration.md#limits)).
- Single sign-on accepts only asymmetrically signed ID tokens and links accounts by issuer and subject, never by e-mail address (see [docs/oidc.md](docs/oidc.md)).
- The audit log on the admin page stores usernames and, for failed logins and rate-limit blocks only, shortened IP addresses; it keeps entries for `AUDIT_RETENTION_DAYS` (default 180).
