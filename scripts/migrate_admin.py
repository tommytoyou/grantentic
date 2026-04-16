"""
One-time migration script: move the Grant admin user from the legacy
data/users.json flat file into the Supabase `users` table.

Reuses the existing hashed_password and salt so the admin can keep their
current password. Safe to re-run: checks if the user already exists in
Supabase and skips insertion if so.

Usage:
    SUPABASE_URL=... SUPABASE_ANON_KEY=... python scripts/migrate_admin.py
"""

import json
import os
import sys
from pathlib import Path

# Make src/ importable when running from the repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.database import get_supabase, get_user_by_username


USERS_FILE = REPO_ROOT / "data" / "users.json"
TARGET_USERNAME = "Grant"


def main() -> int:
    if not USERS_FILE.exists():
        print(f"ERROR: {USERS_FILE} not found. Restore it from git "
              f"(`git show HEAD~1:data/users.json > data/users.json`) "
              f"and re-run this script.")
        return 1

    with open(USERS_FILE, "r") as f:
        users = json.load(f)

    if TARGET_USERNAME not in users:
        print(f"ERROR: user '{TARGET_USERNAME}' not found in {USERS_FILE}.")
        return 1

    entry = users[TARGET_USERNAME]
    hashed_password = entry["password_hash"]
    salt = entry["salt"]
    is_admin = entry.get("role") == "admin"

    existing = get_user_by_username(TARGET_USERNAME)
    if existing:
        print(f"User '{TARGET_USERNAME}' already exists in Supabase "
              f"(id={existing.get('id')}). Skipping insert.")
        return 0

    sb = get_supabase()
    result = sb.table("users").insert({
        "username": TARGET_USERNAME,
        "hashed_password": hashed_password,
        "salt": salt,
        "is_admin": is_admin,
        "plan": "free",
        "submissions_used": 0,
    }).execute()

    inserted = result.data[0] if result.data else None
    if inserted:
        print(f"Migrated '{TARGET_USERNAME}' to Supabase (id={inserted.get('id')}, "
              f"is_admin={inserted.get('is_admin')}).")
        return 0

    print("ERROR: insert returned no data.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
