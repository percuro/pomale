"""Plain SQL dump of the SQLite database to stdout (e.g. for restic --stdin-from-command).

First a consistent in-memory copy via the SQLite backup API, then the dump from that
copy: this yields one consistent state even while the app is writing. Uncompressed,
so deduplicating backup tools only store the changes between runs.
"""

import sqlite3
import sys

from app.config import get_database_url


def database_path() -> str:
    url = get_database_url()
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        raise SystemExit("Only SQLite databases are supported")
    return url[len(prefix) :]


def main() -> None:
    path = database_path()
    source = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30)
    snapshot = sqlite3.connect(":memory:")
    try:
        source.backup(snapshot)
    finally:
        source.close()
    out = sys.stdout
    for line in snapshot.iterdump():
        out.write(line)
        out.write("\n")
    snapshot.close()
    out.flush()


if __name__ == "__main__":
    main()
