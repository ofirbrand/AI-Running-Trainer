#!/usr/bin/env python3
"""One-off migration of the local SQLite database to a hosted Postgres (Neon).

Copies all tables in FK-safe order, preserving primary keys, handling the
training_plans.active_version_id <-> plan_versions circular FK, and resetting
Postgres identity sequences afterwards. Optionally imports the on-disk Garmin
token files into the new garmin_connections.token_data column (DB token store).

Usage (from the repo root, inside the project venv):

    python scripts/migrate_sqlite_to_postgres.py \
        --dest "postgres://...neon.tech/neondb?sslmode=require" \
        [--source backend/data/coach.sqlite3] [--import-tokens] [--force]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from sqlalchemy import create_engine, func, select, text  # noqa: E402

from app import models  # noqa: E402, F401  (registers tables on the metadata)
from app.db import Base  # noqa: E402

# FK-safe insert order. training_plans is inserted with active_version_id
# forced to NULL (it points forward at plan_versions) and fixed up afterwards.
TABLE_ORDER = [
    "users",
    "profiles",
    "garmin_connections",
    "user_settings",
    "metric_observations",
    "activities",
    "daily_health",
    "health_snapshots",
    "training_plans",
    "plan_versions",
    "planned_workouts",
    "workout_completions",
    "plan_change_requests",
]


def normalize_pg_url(url: str) -> str:
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix) and not url.startswith("postgresql+"):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", required=True, help="Destination Postgres URL")
    parser.add_argument(
        "--source",
        default=str(REPO_ROOT / "backend" / "data" / "coach.sqlite3"),
        help="Source SQLite file (default: backend/data/coach.sqlite3)",
    )
    parser.add_argument(
        "--import-tokens",
        action="store_true",
        help="Import backend/data/garmin_tokens/<uid>/garmin_tokens.json into token_data",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Wipe existing destination rows before copying",
    )
    args = parser.parse_args()

    source_path = Path(args.source)
    if not source_path.exists():
        print(f"Source database not found: {source_path}")
        return 1

    src = create_engine(f"sqlite:///{source_path}", future=True)
    dest = create_engine(normalize_pg_url(args.dest), future=True)

    tables = {t.name: t for t in Base.metadata.sorted_tables}
    missing = [name for name in TABLE_ORDER if name not in tables]
    if missing:
        print(f"Model metadata is missing tables: {missing}")
        return 1

    print("Creating destination schema (create_all)...")
    Base.metadata.create_all(dest)

    with dest.begin() as dconn:
        existing_users = dconn.execute(
            select(func.count()).select_from(tables["users"])
        ).scalar_one()
        if existing_users and not args.force:
            print(
                f"Destination already has {existing_users} user(s). "
                "Re-run with --force to wipe and re-copy."
            )
            return 1

    plan_active_versions: dict[int, int] = {}
    counts: dict[str, int] = {}

    with src.connect() as sconn, dest.begin() as dconn:
        if args.force:
            print("Wiping destination tables (--force)...")
            dconn.execute(
                tables["training_plans"].update().values(active_version_id=None)
            )
            for name in reversed(TABLE_ORDER):
                dconn.execute(tables[name].delete())

        for name in TABLE_ORDER:
            table = tables[name]
            rows = [dict(r) for r in sconn.execute(select(table)).mappings()]
            if name == "training_plans":
                for row in rows:
                    if row.get("active_version_id") is not None:
                        plan_active_versions[row["id"]] = row["active_version_id"]
                        row["active_version_id"] = None
            if rows:
                dconn.execute(table.insert(), rows)
            counts[name] = len(rows)
            print(f"  {name}: {len(rows)} rows")

        # Restore the circular FK now that plan_versions exists.
        for plan_id, version_id in plan_active_versions.items():
            dconn.execute(
                tables["training_plans"]
                .update()
                .where(tables["training_plans"].c.id == plan_id)
                .values(active_version_id=version_id)
            )
        if plan_active_versions:
            print(f"  restored active_version_id on {len(plan_active_versions)} plan(s)")

        # Explicit-PK inserts leave Postgres identity sequences behind — reset.
        for name in TABLE_ORDER:
            dconn.execute(
                text(
                    "SELECT setval(pg_get_serial_sequence(:t, 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {name}), 0) + 1, false)"
                ),
                {"t": name},
            )

        if args.import_tokens:
            tokens_root = REPO_ROOT / "backend" / "data" / "garmin_tokens"
            gc = tables["garmin_connections"]
            for row in dconn.execute(select(gc.c.id, gc.c.user_id)).all():
                token_file = tokens_root / str(row.user_id) / "garmin_tokens.json"
                if not token_file.exists():
                    print(f"  no token file for user {row.user_id}; skipping")
                    continue
                blob = token_file.read_text()
                json.loads(blob)  # validate before storing
                dconn.execute(
                    gc.update()
                    .where(gc.c.id == row.id)
                    .values(token_data=blob, token_dir="db")
                )
                print(f"  imported Garmin tokens for user {row.user_id}")

    # Verify per-table row counts.
    mismatched = []
    with src.connect() as sconn, dest.connect() as dconn:
        for name in TABLE_ORDER:
            s = sconn.execute(select(func.count()).select_from(tables[name])).scalar_one()
            d = dconn.execute(select(func.count()).select_from(tables[name])).scalar_one()
            status = "OK" if s == d else "MISMATCH"
            if s != d:
                mismatched.append(name)
            print(f"  verify {name}: source={s} dest={d} {status}")

    if mismatched:
        print(f"Row count mismatch in: {mismatched}")
        return 1
    print("Migration complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
