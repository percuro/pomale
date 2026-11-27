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

Every operation carries `x-pomale-stability`: `stable` or `internal` (see below). The fields of the stable operations are described in the document itself, for example the weekday bit mask, the day states and `base_version`.

## Stability

From 1.0 on, pomale follows [Semantic Versioning](https://semver.org/) for everything you can build on. **Stable until 2.0** are:

- **The API you can reach with a key:** all operations in the table [above](#what-a-key-may-do), and `GET /api/health`. They are marked `x-pomale-stability: stable` in the API description.
- **The error format** `{"detail": "…", "code": "…"}` and the codes [below](#errors).
- **The settings** in [configuration](configuration.md): names, meaning and defaults.
- **The JSON export** `pomale-export` version 1, and the CSV export's columns and values.
- **The data volume:** every 1.x starts on the data of an earlier one and migrates it.

Within 1.x, nothing of this is removed or renamed, no request field becomes required, no limit becomes stricter and no field that always had a value becomes null. What may be added: operations, optional request fields, response fields, error codes and values of an enum (a new day state, for example). So **ignore fields and values you do not know** instead of failing on them. A test in every build compares the stable API with the one of 1.0.0.

**Internal** are all other operations under `/api/v1`: signing in, the account, devices, keys, setup, administration, and creating or changing habits, groups and pauses. They serve the web app and may change in any release; their description ends with "Internal".

**Deprecated** things are marked first: `deprecated: true` in the API description, a warning in the log for settings, and the section "Deprecated" in the [changelog](../CHANGELOG.md). They keep working and are removed in 2.0 at the earliest. `/api/v1` stays the path for all of 1.x.

Not part of the promise: the wording of `detail`, `message`, `status` and `progress` (they are for people and can be improved; automations use `code`, `state` and `result`), and the web app's look.

## Errors

Every error is JSON with a `code` that stays the same, and an English `detail` that may change:

```json
{"detail": "Future days cannot be checked off", "code": "checkin.future_day"}
```

| Status | `code` | Meaning |
|---|---|---|
| 401 | `token.invalid` | The key is unknown, expired or revoked |
| 403 | `token.not_allowed` | A key cannot reach this operation |
| 403 | `token.missing_scope` | The key lacks the scope (`read` or `checkin`) |
| 403 | `token.all_habits_needed` | This operation needs a key for all habits |
| 403 | `token.habit_not_allowed` | The key is limited to other habits |
| 404 | `habit.not_found` | No such habit in this account |
| 409 | `habit.archived` | The habit is archived (shortcut) |
| 409 | `checkin.conflict` | The day changed since `base_version`; the current state is in `server` |
| 411 | `request.length_required` | A request body needs a `Content-Length` |
| 413 | `request.too_large` | The body is larger than 1 MB |
| 422 | `validation` | Invalid input; `errors` lists `field`, `type` and `message` |
| 422 | `checkin.future_day`, `note.future_day` | Days after today cannot be checked off or get a note |
| 422 | `checkin.value_not_allowed` | `value` is only for quantity goals |
| 422 | `shortcut.done_only` | `PUT …/days/today` only checks off, it does not undo |
| 422 | `range.end_before_start` | `to` is before `from` |
| 422 | `range.too_long` | The range is too long; the limit is in `max_days` |
| 429 | `auth.rate_limited` | Too many wrong keys from this address; wait for `Retry-After` seconds |
| 503 | `health.database_unavailable` | The database cannot be reached |
| any | `http.<status>` | Other errors of the web server, e.g. `http.404` for an unknown path |

Operations of the web app have further codes; they are internal.

## Export and import

"Account" → **Your data** ("Deine Daten"):

- **CSV** for spreadsheet programs: one row per habit and day, separated by `;`, in UTF-8 with a byte order mark. The columns are always `date;habit;cue;planned;state;value;target;note`, in every language: `planned` is `yes` or `no`, `state` one of the day states of the API (`done`, `open`, `partial`, `extra_done`, `not_planned`, `paused`). New columns only ever go at the end.
- **JSON** with everything of the account: habits with their plans, reminder times, check-ins and notes, groups, pauses, and the settings time zone, language and day end. Not included: username, password, sign-in links, sessions, devices, keys and the audit log.

A JSON export can be **imported** into an account that has no habits, groups and pauses yet, for example a new account on another instance. The import takes all or nothing; the file is checked first (at most 5 MB). Check-ins keep their days; reminder times start fresh.

The format is `{"format": "pomale-export", "version": 1, …}`; an example is [backend/tests/fixtures/export_v1.json](../backend/tests/fixtures/export_v1.json). From 1.0 on, version 1 only gets new fields, nothing is renamed or removed.

Admins can do the same on the server, e.g. to move accounts between instances:

```bash
docker compose exec -T app python -m app.cli.export_account alex > alex.json
docker compose exec -T app python -m app.cli.import_account alex < alex.json   # into an empty account
```
