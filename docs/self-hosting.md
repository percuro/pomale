# Self-hosting

You need a Linux host with Docker and Docker Compose, a domain name pointing to it, and a reverse proxy that terminates TLS. HTTPS is required in practice: browsers only allow the offline service worker and "Add to Home Screen" on secure origins (and `localhost`).

## Install

```bash
mkdir habits && cd habits
curl -fsSLO https://raw.githubusercontent.com/percuro/pomale/main/compose.yaml
echo "PUBLIC_URL=https://habits.example.org" > .env
docker compose up -d
docker compose logs app
```

The log shows a block like this while no account exists:

```
No account exists yet. Open https://habits.example.org/setup and enter this setup token:

    3pX…

```

Open that address, enter the token and choose a username and password (at least 12 characters). This first account is an admin. The token is only valid until the first account exists. A restart without an account issues a new token; use the most recent one. Alternatively create the account on the command line:

```bash
docker compose exec app python -m app.cli.create_user alex
```

The container listens on `127.0.0.1:8000` only. Put one of the following reverse proxies in front.

## Reverse proxy

### Caddy (simplest, automatic certificates)

On the host, `/etc/caddy/Caddyfile`:

```
habits.example.org {
    reverse_proxy 127.0.0.1:8000
}
```

Or as part of the same Compose project – replace the `ports:` section of the app with nothing and add:

```yaml
  caddy:
    image: caddy:2
    restart: unless-stopped
    ports: ["80:80", "443:443"]
    command: caddy reverse-proxy --from habits.example.org --to app:8000
    volumes:
      - caddy_data:/data
volumes:
  caddy_data:
```

### Traefik

Labels on the `app` service (remove `ports:`; the app must share a network with Traefik):

```yaml
    labels:
      - traefik.enable=true
      - traefik.http.routers.habits.rule=Host(`habits.example.org`)
      - traefik.http.routers.habits.entrypoints=websecure
      - traefik.http.routers.habits.tls.certresolver=letsencrypt
      - traefik.http.services.habits.loadbalancer.server.port=8000
```

### Nginx Proxy Manager

Add a proxy host for `habits.example.org` → scheme `http`, forward host `127.0.0.1` (or the app's container name if NPM shares a Docker network with it), port `8000`; request a Let's Encrypt certificate and enable "Force SSL".

### Any other proxy

Forward everything to port 8000 and pass `Host`, `X-Forwarded-For` and `X-Forwarded-Proto`. No path rewriting, no special routes: the app serves both `/api` and the web interface.

## Updates

```bash
docker compose exec app python -m app.cli.backup   # backup first (into /data/backups)
docker compose pull
docker compose up -d
docker compose logs --tail=50 app
```

Database migrations run automatically when the container starts. The image tag `:0` follows all 0.x releases; pin a specific version (e.g. `:0.4.0`) if you prefer to update deliberately. Read the [changelog](../CHANGELOG.md) before major updates.

## Backup and restore

All data is one SQLite file on the `data` volume.

### Built-in backups

pomale backs itself up **every day at 03:00** (in `DEFAULT_TIMEZONE`): a compressed SQL dump of a consistent snapshot in `/data/backups`, named `pomale-YYYYMMDD-HHMM.sql.gz` (UTC). Backups older than 14 days are deleted, the newest one always stays. A new instance, or one that was down at backup time, backs up a minute after it starts. Admins see the state under "Administration" → **Backups** and can back up now; there is no download, because admins do not see other accounts' data. Settings: `BACKUP_ENABLED`, `BACKUP_TIME`, `BACKUP_KEEP_DAYS`, `BACKUP_DIR` ([configuration](configuration.md)).

**These backups lie on the same volume as the database.** They help after a mistake or a broken database file, not when the disk or server is lost. Copy them somewhere else as well, e.g. with restic, borg or rsync from the volume's directory, or use the dump below.

Back up now from the command line:

```bash
docker compose exec app python -m app.cli.backup
```

### A dump for your own backup tool

A consistent plain-SQL dump to stdout while the app is running:

```bash
docker compose exec -T app python -m app.cli.dump_sql > habits.sql
```

It is uncompressed on purpose so that deduplicating backup tools such as restic or borg store only the changes. Example nightly cron job with restic:

```cron
30 3 * * * cd /srv/habits && restic backup --stdin-filename habits.sql --stdin-from-command -- docker compose exec -T app python -m app.cli.dump_sql
```

If you back up this way, you can turn the built-in backups off with `BACKUP_ENABLED=false`, or keep both.

### Restore

Restore into an empty data volume (the command refuses to overwrite an existing database). From a built-in backup:

```bash
docker compose stop app
docker compose run --rm --no-deps app sh -c 'mv /data/habits.db /data/habits.db.before-restore 2>/dev/null; rm -f /data/habits.db-wal /data/habits.db-shm'
docker compose run --rm --no-deps app python -m app.cli.restore_sql --from /data/backups/pomale-20261124-0200.sql.gz
docker compose up -d
```

From a dump file on the host, replace the third line with:

```bash
docker compose run --rm --no-deps -T app python -m app.cli.restore_sql < habits.sql
```

Test a restore now and then; a backup you never restored is a hope, not a backup.

Backups also contain the key pair pomale uses for reminders (Web Push). Restoring one keeps every device's reminders working; starting with an empty database or another instance's backup means devices have to turn reminders on again.

To move **one account** rather than the whole instance, use the JSON export and import ([API](api.md#export-and-import)).

## Users and invitations

Every account has its own habits, time zone and language. Nobody, not even an admin, sees another account's habits or check-ins.

- **Roles.** `admin` accounts may manage accounts; `user` accounts only their own data. The account created in the first-run setup is an admin; after an upgrade from 0.3 every existing account is an admin.
- **Inviting.** Admin page → "Invite someone": choose the role and an optional note, create the link and send it yourself (copy it, or on a phone use the share sheet). The link works once and is valid for `INVITE_EXPIRY_DAYS` days (default 7). Open links are listed and can be revoked. The instance sends no e-mail.
- **Forgotten passwords.** Admin page → the account → "Recovery link". The person opens it and sets a new password (or links a provider account, with single sign-on); the link is valid for 24 hours, only the newest one works, and all devices of that account are logged out. Admins never see or set a password.
- **Single sign-on.** With an OpenID Connect provider (Authelia, Authentik, Pocket ID, …) people can sign in there instead of with a pomale password: through an invitation, by linking their account on the account page, or automatically. See [Single sign-on](oidc.md).
- **Deactivating** logs the account out everywhere at once and stops its shortcut keys; its data stays until you reactivate or delete it. **Deleting** removes the account with all its data. People can also delete their own account on the account page.
- **The last active admin** cannot be demoted, deactivated or deleted.
- **Open registration:** with `REGISTRATION=open` a "Register" link appears on the login page; new accounts get the role user. For a private instance, invitations are the better choice.

What admins see about other accounts: username, display name, role, active or deactivated, how it signs in (password, provider), when it was created and when it was last active. Sessions store a coarse device name (e.g. "iPhone · Safari") for the owner's device list; no IP addresses are stored with them.

**Audit log.** Admin page → "Log" lists security-relevant events: logins and failed logins, rate-limit blocks, created and deleted accounts, password changes, role changes, (de)activation, invitations and recovery links, provider links and shortcut keys, also when done on the command line. It stores usernames (kept after an account is deleted) and, only for failed logins and rate-limit blocks, the shortened IP address (IPv4 /24, IPv6 /48). Entries are deleted after `AUDIT_RETENTION_DAYS` (default 180).

### Command line

```bash
docker compose exec app python -m app.cli.create_user <name>                   # new account (role user; the very first one is admin)
docker compose exec app python -m app.cli.create_user <name> --role admin      # new admin
docker compose exec app python -m app.cli.create_user <name> --reset-password  # new password, logs out all devices
docker compose exec app python -m app.cli.set_role <name> admin                # emergency exit: make an account admin again
```

## Monitoring

`GET /api/health` returns `{"status": "ok", "version": "…"}` when the app and its database work, otherwise HTTP 503. The image also defines a Docker health check.

## Reminders

Reminders (Web Push) are on by default and need two things: HTTPS (browsers allow push only on secure pages; `http://localhost` works for testing) and outgoing HTTPS from the container to the push services of Google, Apple, Mozilla and Microsoft. See [Reminders](reminders.md) and the `PUSH_*` variables in the [configuration](configuration.md).

## iPhone

See [iphone.md](iphone.md) for the home-screen web app, offline use, reminders and the shortcut widget.
