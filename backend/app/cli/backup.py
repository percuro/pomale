"""Write a backup now into BACKUP_DIR (the same as the daily one) and prune old ones.

python -m app.cli.backup
"""

from datetime import UTC, datetime

from app.config import get_backup_dir, get_backup_keep_days
from app.services.backup_service import create_backup


def main() -> None:
    backup = create_backup(get_backup_dir(), datetime.now(UTC), get_backup_keep_days())
    print(f"{backup.path} ({backup.size} bytes)")


if __name__ == "__main__":
    main()
