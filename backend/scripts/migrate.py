"""Apply the versioned SQL migrations in backend/migrations (idempotent)."""

import hashlib
import pathlib
import sys

from sqlalchemy import text

from app.db import engine

MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parent.parent / "migrations"


def main() -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version TEXT PRIMARY KEY, "
            "checksum TEXT NOT NULL, "
            "applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        applied = {
            version: checksum
            for version, checksum in conn.execute(
                text("SELECT version, checksum FROM schema_migrations")
            ).all()
        }

    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        sys.exit(f"No migrations found in {MIGRATIONS_DIR}")

    for path in files:
        sql = path.read_text()
        checksum = hashlib.sha256(sql.encode()).hexdigest()
        if path.name in applied:
            if applied[path.name] != checksum:
                sys.exit(f"{path.name} was modified after being applied — add a new migration")
            continue
        with engine.begin() as conn:
            conn.exec_driver_sql(sql)
            conn.execute(
                text("INSERT INTO schema_migrations (version, checksum) VALUES (:v, :c)"),
                {"v": path.name, "c": checksum},
            )
        print(f"applied {path.name}")

    print("database schema is up to date")


if __name__ == "__main__":
    main()
