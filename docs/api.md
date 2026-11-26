# API and API keys

The web app talks to pomale through a JSON API under `/api`. With a personal **API key** you can use part of it from scripts, iOS shortcuts and home automation such as Home Assistant.

## API keys

"Account" ("Konto") → **API keys** ("API-Schlüssel"): give the key a name, choose what it may do and, if you like, which habits and for how long. The key (`pm_…`) is shown **once**; only a hash of it is stored. Revoke it on the same page at any time. An account can have 50 active keys.

Send it as a header:

```
Authorization: Bearer pm_…
```

A key never needs a CSRF header or a cookie. If a request carries the session cookie of the web app as well, the cookie counts and the key is ignored.

### What a key may do

| Permission | Scope | Endpoints |
|---|---|---|
| Read ("Lesen") | `read` | `GET /api/v1/today`, `/api/v1/days`, `/api/v1/habits`, `/api/v1/groups`, `/api/v1/pauses`, `/api/v1/history`, `/api/v1/export.csv`, `/api/v1/export.json` |
| Check off ("Abhaken") | `checkin` | `PUT /api/v1/habits/{id}/days/{date}`, `PUT /api/v1/habits/{id}/days/{date}/note`, `PUT /api/v1/habits/{id}/days/today` |

Nothing else is reachable with a key: not the account, its sessions, devices or keys, not creating or changing habits, groups or pauses, not the administration. Such requests get `403` with `code` `token.not_allowed`; a missing permission gives `token.missing_scope`.

A key **limited to some habits** sees only those in `/today`, `/days` and `/habits` and can only check them off. History, exports, groups and pauses need a key for all habits (`token.all_habits_needed`), because their answers sum up all habits.

The shortcut keys from the habits page ([iPhone](iphone.md)) are keys with "check off" for exactly one habit. They appear in the same list.

Wrong keys are counted per IP address: after 20 within 15 minutes, that address gets `429` for a while.

## Examples

What is still open today, as one sentence and as a list:

```bash
curl -H "Authorization: Bearer pm_…" https://habits.example.org/api/v1/today
```

```json
{
  "date": "2026-11-24",
  "due": 4,
  "done": 1,
  "open": [
    {"id": 3, "name": "Read", "cue": "after dinner", "goal_type": "days", "state": "open",
     "value": null, "target": null, "unit": null, "week": null, "progress": null},
    {"id": 5, "name": "Water", "cue": null, "goal_type": "quantity", "state": "partial",
     "value": 3, "target": 8, "unit": "glasses", "week": null, "progress": "3 of 8 glasses"}
  ],
  "message": "Still open: Read, Water (3 of 8 glasses)"
}
```

`message` is in the account's language (else the `Accept-Language` of the request). "Today" is the account's day, including its time zone and day end.

Check off a habit for a given day (needs `checkin`); quantity goals take `value` instead of `done`:

```bash
curl -X PUT -H "Authorization: Bearer pm_…" -H "Content-Type: application/json" \
  -d '{"done": true}' https://habits.example.org/api/v1/habits/3/days/2026-11-24
```

Or for today, as the server sees it (this is what the iOS shortcut does; quantity goals add 1, or `amount`):

```bash
curl -X PUT -H "Authorization: Bearer pm_…" https://habits.example.org/api/v1/habits/3/days/today
```

Everything of the account as JSON (see [Export and import](#export-and-import)):

```bash
curl -H "Authorization: Bearer pm_…" -o pomale.json https://habits.example.org/api/v1/export.json
```

### Home Assistant

A sensor with the number of open habits and the sentence as an attribute (`configuration.yaml`; the key in `secrets.yaml`):

```yaml
rest:
  - resource: https://habits.example.org/api/v1/today
    headers:
      Authorization: !secret pomale_key   # "Bearer pm_…"
    scan_interval: 300
    sensor:
      - name: "Habits open"
        value_template: "{{ value_json.open | length }}"
        json_attributes:
          - message
          - open

rest_command:
  pomale_meds_done:
    url: https://habits.example.org/api/v1/habits/7/days/today
    method: put
    headers:
      Authorization: !secret pomale_key
```

For the `rest_command`, a key limited to that one habit with "check off" is enough.

### iOS: "What is still open?"

See [iPhone](iphone.md#what-is-still-open-siri): one action, and Siri reads the answer.

## The API description

`/api/openapi.json` describes every endpoint (OpenAPI 3). Import it into Postman, Bruno, Insomnia or a code generator; operations a key can use are marked with their scope. It is served unless `API_DOCS=false` ([configuration](configuration.md)). There is no documentation page on the server itself.

Until 1.0 the API can still change; changes are listed under "Upgrade notes" in the [changelog](../CHANGELOG.md).

## Export and import

"Account" → **Your data** ("Deine Daten"):

- **CSV** for spreadsheet programs: one row per habit and day.
- **JSON** with everything of the account: habits with their plans, reminder times, check-ins and notes, groups, pauses, and the settings time zone, language and day end. Not included: username, password, sign-in links, sessions, devices, keys and the audit log.

A JSON export can be **imported** into an account that has no habits, groups and pauses yet, for example a new account on another instance. The import takes all or nothing; the file is checked first (at most 5 MB). Check-ins keep their days; reminder times start fresh.

The format is `{"format": "pomale-export", "version": 1, …}`; an example is [backend/tests/fixtures/export_v1.json](../backend/tests/fixtures/export_v1.json). From 1.0 on, version 1 only gets new fields, nothing is renamed or removed.

Admins can do the same on the server, e.g. to move accounts between instances:

```bash
docker compose exec -T app python -m app.cli.export_account alex > alex.json
docker compose exec -T app python -m app.cli.import_account alex < alex.json   # into an empty account
```
