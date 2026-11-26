#!/usr/bin/env bash
# Upgrade test: an instance of an earlier release gets data, then the new image starts on the same
# volume. Everything that existed must still be there and work, including a shortcut key.
#
#   e2e/upgrade/run.sh ghcr.io/percuro/pomale:0.3.0 app:ci
#
# Uses only API calls that exist since 0.3.0. ENGINE=podman for local runs; PORT (default 8000).
set -euo pipefail

FROM_IMAGE=${1:?usage: run.sh <old image> <new image>}
TO_IMAGE=${2:?usage: run.sh <old image> <new image>}
ENGINE=${ENGINE:-docker}
PORT=${PORT:-8000}
BASE="http://localhost:$PORT"
NAME=pomale-upgrade
VOLUME=pomale-upgrade-data
PASSWORD="upgrade-test-password-1"

remove_instance() {
  $ENGINE rm -f "$NAME" >/dev/null 2>&1 || true
  $ENGINE volume rm -f "$VOLUME" >/dev/null 2>&1 || true
}
remove_instance
WORK=$(mktemp -d)
JAR="$WORK/cookies"
trap 'remove_instance; rm -rf "$WORK"' EXIT

log() { printf '\n== %s\n' "$*"; }

start() {
  # The command of every release, with the port configurable for local runs
  $ENGINE run -d --name "$NAME" --network host -v "$VOLUME:/data" \
    -e PUBLIC_URL="$BASE" -e PUSH_ALLOWED_HOSTS=push.invalid "$1" \
    sh -c "alembic upgrade head && exec uvicorn app.web:application --host 127.0.0.1 --port $PORT" >/dev/null
  for _ in $(seq 1 60); do
    if curl -fsS "$BASE/api/health" >/dev/null 2>&1; then return 0; fi
    sleep 1
  done
  $ENGINE logs "$NAME"
  echo "$1 did not become healthy" >&2
  exit 1
}

stop() {
  $ENGINE stop -t 20 "$NAME" >/dev/null
  $ENGINE rm "$NAME" >/dev/null
}

# A JSON request with the session cookie and the CSRF header; prints the body, fails on HTTP errors
api() {
  local method=$1 path=$2 body=${3:-}
  local args=(-fsS -X "$method" -b "$JAR" -c "$JAR" -H "X-Habit-CSRF: 1" -H "Origin: $BASE")
  if [ -n "$body" ]; then args+=(-H "Content-Type: application/json" --data "$body"); fi
  curl "${args[@]}" "$BASE/api$path"
}

json() { python3 -c "import json, sys; data = json.load(sys.stdin); print($1)"; }

# Rows by their columns that every release has, so a changed schema does not matter
snapshot() {
  $ENGINE exec -i "$NAME" python - <<'PY'
import sqlite3

db = sqlite3.connect("file:/data/habits.db?mode=ro", uri=True)
print(db.execute("SELECT id, username, is_active FROM users ORDER BY id").fetchall())
print(db.execute("SELECT id, name, archived_on FROM habits ORDER BY id").fetchall())
print(db.execute("SELECT habit_id, local_date, done FROM checkins ORDER BY 1, 2").fetchall())
tables = {name for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
keys = "api_tokens" if "api_tokens" in tables else "shortcut_tokens"
print(db.execute(f"SELECT id, token_hash, revoked_at FROM {keys} ORDER BY id").fetchall())
PY
}

day() { date -u -d "$1 days ago" +%F; }

log "Start $FROM_IMAGE"
start "$FROM_IMAGE"
token=$($ENGINE logs "$NAME" 2>&1 | grep -E '^    [A-Za-z0-9_-]{20,}$' | tail -1 | tr -d ' ')
test -n "$token"

log "Create data with $FROM_IMAGE"
api POST /v1/setup "{\"token\": \"$token\", \"username\": \"upgrade\", \"password\": \"$PASSWORD\"}" >/dev/null
api POST /v1/auth/login "{\"username\": \"upgrade\", \"password\": \"$PASSWORD\"}" >/dev/null
start_on=$(day 30)
read_id=$(api POST /v1/habits "{\"name\": \"Lesen\", \"start_on\": \"$start_on\"}" | json 'data["id"]')
run_id=$(api POST /v1/habits "{\"name\": \"Laufen\", \"weekdays\": 21, \"start_on\": \"$start_on\"}" | json 'data["id"]')
old_id=$(api POST /v1/habits "{\"name\": \"Alt\", \"start_on\": \"$start_on\"}" | json 'data["id"]')
for ago in 1 2 3 5 8; do api PUT "/v1/habits/$read_id/days/$(day $ago)" '{"done": true}' >/dev/null; done
api PUT "/v1/habits/$read_id/days/$(day 4)" '{"done": false}' >/dev/null
api PUT "/v1/habits/$run_id/days/$(day 2)" '{"done": true}' >/dev/null
api POST "/v1/habits/$old_id/archive" >/dev/null
key=$(api POST "/v1/habits/$read_id/shortcut-tokens" '{"label": "iPhone"}' | json 'data["token"]')
revoked=$(api POST "/v1/habits/$read_id/shortcut-tokens" '{"label": "old"}' | json 'data["id"]')
api DELETE "/v1/habits/$read_id/shortcut-tokens/$revoked" >/dev/null
before=$(snapshot)
echo "$before"
stop

log "Upgrade to $TO_IMAGE"
start "$TO_IMAGE"
$ENGINE exec "$NAME" alembic current 2>&1 | tee "$WORK/current"
grep -q "(head)" "$WORK/current"
after=$(snapshot)
if [ "$before" != "$after" ]; then
  echo "Data changed by the upgrade" >&2
  diff <(echo "$before") <(echo "$after") >&2 || true
  exit 1
fi
echo "Rows unchanged"

log "Use the upgraded instance"
rm -f "$JAR"
api POST /v1/auth/login "{\"username\": \"upgrade\", \"password\": \"$PASSWORD\"}" >/dev/null
api GET "/v1/days?from=$(day 8)&to=$(day 0)" | json '[(h["name"], h["archived"]) for h in data["habits"]]'
api GET /v1/today | json 'data["message"]'
# The shortcut key from the old release still checks off its habit, without cookie and CSRF header
curl -fsS -X PUT -H "Authorization: Bearer $key" -H "Content-Type: application/json" --data '{"done": true}' \
  "$BASE/api/v1/habits/$read_id/days/today" | json 'data["habit_name"]'
status=$(curl -s -o /dev/null -w '%{http_code}' -X PUT -H "Authorization: Bearer $key" \
  "$BASE/api/v1/habits/$run_id/days/today")
test "$status" = 403

log "Back up and restore the upgraded instance"
$ENGINE exec "$NAME" python -m app.cli.backup
file=$($ENGINE exec "$NAME" sh -c 'ls -t /data/backups/pomale-*.sql.gz | head -1')
$ENGINE exec "$NAME" python -m app.cli.restore_sql --from "$file" --target /tmp/restored.db
$ENGINE exec -i "$NAME" python - <<'PY'
import sqlite3

live = sqlite3.connect("file:/data/habits.db?mode=ro", uri=True)
restored = sqlite3.connect("/tmp/restored.db")
query = "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
for (table,) in live.execute(query):
    counts = [db.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0] for db in (live, restored)]
    assert counts[0] == counts[1], f"{table}: {counts}"
print("Backup restores every row")
PY

log "Upgrade from $FROM_IMAGE passed"
