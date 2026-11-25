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
docker compose exec -T app python -m app.cli.dump_sql > backup-$(date +%F).sql   # backup first
docker compose pull
docker compose up -d
docker compose logs --tail=50 app
```

Database migrations run automatically when the container starts. The image tag `:0` follows all 0.x releases; pin a specific version (e.g. `:0.4.0`) if you prefer to update deliberately. Read the [changelog](../CHANGELOG.md) before major updates.

## Backup and restore

All data is one SQLite file on the `data` volume. Create a consistent plain-SQL dump while the app is running:

```bash
docker compose exec -T app python -m app.cli.dump_sql > habits.sql
```

The dump is uncompressed on purpose so that deduplicating backup tools such as restic or borg store only the changes. Example nightly cron job with restic:

```cron
30 3 * * * cd /srv/habits && restic backup --stdin-filename habits.sql --stdin-from-command -- docker compose exec -T app python -m app.cli.dump_sql
```

Restore into an empty data volume (the command refuses to overwrite an existing database):

```bash
docker compose stop app
docker compose run --rm --no-deps app sh -c 'mv /data/habits.db /data/habits.db.before-restore 2>/dev/null; rm -f /data/habits.db-wal /data/habits.db-shm'
docker compose run --rm --no-deps -T app python -m app.cli.restore_sql < habits.sql
docker compose up -d
```

Test a restore now and then; a backup you never restored is a hope, not a backup.

## Users and invitations

Every account has its own habits, time zone and language. Nobody, not even an admin, sees another account's habits or check-ins.

- **Roles.** `admin` accounts may manage accounts; `user` accounts only their own data. The account created in the first-run setup is an admin; after an upgrade from 0.3 every existing account is an admin.
- **Inviting.** Admin page → "Invite someone": choose the role and an optional note, create the link and send it yourself (copy it, or on a phone use the share sheet). The link works once and is valid for `INVITE_EXPIRY_DAYS` days (default 7). Open links are listed and can be revoked. The instance sends no e-mail.
- **Forgotten passwords.** Admin page → the account → "Password-reset link". The person opens it and sets a new password; the link is valid for 24 hours, only the newest one works, and all devices of that account are logged out. Admins never see or set a password.
- **Deactivating** logs the account out everywhere at once and stops its shortcut keys; its data stays until you reactivate or delete it. **Deleting** removes the account with all its data. People can also delete their own account on the account page.
- **The last active admin** cannot be demoted, deactivated or deleted.
- **Open registration:** with `REGISTRATION=open` a "Register" link appears on the login page; new accounts get the role user. For a private instance, invitations are the better choice.

What admins see about other accounts: username, display name, role, active or deactivated, when it was created and when it was last active. Sessions store a coarse device name (e.g. "iPhone · Safari") for the owner's device list; no IP addresses are stored.

### Command line

```bash
docker compose exec app python -m app.cli.create_user <name>                   # new account (role user; the very first one is admin)
docker compose exec app python -m app.cli.create_user <name> --role admin      # new admin
docker compose exec app python -m app.cli.create_user <name> --reset-password  # new password, logs out all devices
docker compose exec app python -m app.cli.set_role <name> admin                # emergency exit: make an account admin again
```

## Monitoring

`GET /api/health` returns `{"status": "ok", "version": "…"}` when the app and its database work, otherwise HTTP 503. The image also defines a Docker health check.

## iPhone

See [iphone.md](iphone.md) for the home-screen web app, offline use and the shortcut widget.
