import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path("orvyn.db")
BACKUP_DIR = Path("backups")

BACKUP_DIR.mkdir(exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_path = BACKUP_DIR / f"orvyn_before_fk_repair_{timestamp}.db"

# Create a consistent SQLite backup before changing anything.
with sqlite3.connect(DB_PATH) as source:
    with sqlite3.connect(backup_path) as backup:
        source.backup(backup)

with sqlite3.connect(backup_path) as backup:
    integrity = backup.execute(
        "PRAGMA integrity_check"
    ).fetchone()[0]

if integrity != "ok":
    raise RuntimeError("Backup integrity check failed")

print("Backup:", backup_path.resolve())
print("Backup integrity:", integrity)

with sqlite3.connect(DB_PATH) as db:
    db.execute("PRAGMA foreign_keys=ON")

    violations = db.execute(
        "PRAGMA foreign_key_check"
    ).fetchall()

    if not violations:
        print("No foreign-key violations found.")
        raise SystemExit(0)

    expected_table = "message_web_sources"
    expected_parent = "messages"

    if any(
        table != expected_table or parent != expected_parent
        for table, rowid, parent, fk_index in violations
    ):
        raise RuntimeError(
            "Unexpected foreign-key violations. Repair cancelled."
        )

    orphan_rows = db.execute("""
        SELECT id
        FROM message_web_sources
        WHERE NOT EXISTS (
            SELECT 1
            FROM messages
            WHERE messages.id = message_web_sources.message_id
        )
    """).fetchall()

    if len(orphan_rows) != len(violations):
        raise RuntimeError(
            "Orphan count does not match foreign-key violations."
        )

    if len(orphan_rows) != 15:
        raise RuntimeError(
            "Expected exactly 15 orphan records. Repair cancelled."
        )

    print("Orphan records identified:", len(orphan_rows))

    try:
        db.execute("BEGIN IMMEDIATE")

        db.execute("""
            DELETE FROM message_web_sources
            WHERE NOT EXISTS (
                SELECT 1
                FROM messages
                WHERE messages.id = message_web_sources.message_id
            )
        """)

        remaining = db.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if remaining:
            raise RuntimeError(
                "Foreign-key violations remain. Rolling back."
            )

        db.commit()

    except Exception:
        db.rollback()
        raise

with sqlite3.connect(DB_PATH) as db:
    print(
        "Remaining foreign-key violations:",
        len(db.execute("PRAGMA foreign_key_check").fetchall()),
    )
    print(
        "Database integrity:",
        db.execute("PRAGMA integrity_check").fetchone()[0],
    )

print("Repair completed successfully.")