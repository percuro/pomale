"""Plain SQL dump of the SQLite database to stdout (e.g. for restic --stdin-from-command).

First a consistent in-memory copy via the SQLite backup API, then the dump from that
copy: this yields one consistent state even while the app is writing. Uncompressed,
so deduplicating backup tools only store the changes between runs.
"""

import sys

from app.services.backup_service import database_path, write_dump

__all__ = ["database_path", "main"]


def main() -> None:
    write_dump(sys.stdout)
    sys.stdout.flush()


if __name__ == "__main__":
    main()
