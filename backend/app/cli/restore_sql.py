"""Load an SQL dump from stdin into a new SQLite database.

Never overwrites: if the target file exists, the command stops.
"""

import argparse
import os
import sqlite3
import sys

from app.cli.dump_sql import database_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Load an SQL dump from stdin into a new database")
    parser.add_argument("--target", help="target file (default: path from DATABASE_URL)")
    args = parser.parse_args()
    target = args.target or database_path()
    if os.path.exists(target):
        raise SystemExit(f"{target} already exists; move it away first, nothing is overwritten")

    script = sys.stdin.read()
    if "CREATE TABLE" not in script:
        raise SystemExit("Input does not look like an SQL dump")

    partial = f"{target}.restore-tmp"
    if os.path.exists(partial):
        os.remove(partial)
    connection = sqlite3.connect(partial)
    try:
        connection.executescript(script)
        connection.commit()
        check = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if check != "ok":
            raise SystemExit(f"Integrity check failed: {check}")
        counts = {
            table: connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
            for (table,) in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        }
    finally:
        connection.close()
    os.replace(partial, target)
    for table, count in counts.items():
        print(f"{table}: {count}", file=sys.stderr)
    print(f"Restored to {target}", file=sys.stderr)


if __name__ == "__main__":
    main()
