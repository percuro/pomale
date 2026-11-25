# pomale

> **pomale** (po-MAH-leh): Austrian for "take it slow".

Habits grow at their own pace. pomale is a small, self-hosted habit tracker for your phone and your laptop. Check off a habit in a second on the iPhone, review and correct the week on a big screen. No points, no streaks that reset to zero, no notes you have to write.

> Status: 0.4 – several accounts with invitations, English and German interface. OIDC login is next on the [roadmap](#roadmap).

## Features

- **Today view:** one tap marks a habit done, "undo" sits right next to it, and the row never jumps away.
- **Week view:** habits × days, fully keyboard-operable, with an honest quota like "4 of 5 due days" instead of a streak.
- **Schedules:** daily or on chosen weekdays. Plan changes take effect from a date, so past weeks keep their numbers. Not planned, open and done are different states; extra check-ins on unplanned days never hurt the quota.
- **Works offline:** installable web app (iPhone home screen, Android, desktop). Changes made offline are queued, marked, and sent when the app is back online. A conflicting change from another device is shown to you, never silently overwritten.
- **iOS shortcut widget:** a revocable key for exactly one habit lets an iOS Shortcut check it off from the home screen.
- **For a family, a flat share or a club:** admins invite people with a one-time link; everyone has their own habits, time zone and language, and nobody sees anyone else's data.
- **English and German**, following the browser or the account's choice.
- **CSV export**, plain SQL backups, health endpoint.
- **Small footprint:** one container, one SQLite file, no external services.

## Quick start

```bash
mkdir habits && cd habits
curl -fsSLO https://raw.githubusercontent.com/percuro/pomale/main/compose.yaml
echo "PUBLIC_URL=https://habits.example.org" > .env
docker compose up -d && docker compose logs app   # shows the one-time setup token
```

Then point a TLS reverse proxy at `127.0.0.1:8000` and open `https://habits.example.org/setup`. Details: [docs/self-hosting.md](docs/self-hosting.md).

## Documentation

- [Self-hosting](docs/self-hosting.md): install, reverse proxy (Caddy, Traefik, Nginx Proxy Manager), users and invitations, updates, backup and restore
- [Configuration](docs/configuration.md): all environment variables
- [iPhone](docs/iphone.md): home-screen app, offline use, shortcut widget
- [Development](docs/development.md): running and testing from source
- [Design notes](docs/design.md): why it works the way it does

## Roadmap

- ~~**0.4** multiple accounts with invitations, per-account time zone, English and German interface~~ ✓
- **0.5** login via OpenID Connect (Authelia, Authentik, Pocket ID, …)
- **0.6** weekly targets ("3× a week"), quantities, pauses, history view
- **0.7** reminders via Web Push
- **0.8** personal API tokens, JSON export/import, built-in scheduled backups
- **0.9** beta hardening (accessibility, performance, upgrade tests)
- **1.0** stable API and configuration

## License

Source-available under the [PolyForm Noncommercial License 1.0.0](LICENSE) with an [addendum](LICENSE-ADDENDUM.md):

- **Free** for personal use and for non-profit organisations, including clubs and associations, also when they host it for their members.
- **Commercial use requires a license**: for example offering it as a paid hosted service or using it inside a company. See [COMMERCIAL.md](COMMERCIAL.md).

Contributions are welcome under the [Contributor License Agreement](CLA.md); see [CONTRIBUTING.md](CONTRIBUTING.md).
