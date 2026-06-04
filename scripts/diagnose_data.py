#!/usr/bin/env python3
"""Check Firestore portfolio data and credentials (run from repo root)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
load_dotenv(override=True)


def main() -> None:
    print("Project:", __import__("os").getenv("FIREBASE_PROJECT_ID", "(not set)"))
    try:
        from api import sheets

        df = sheets.read_portfolios(use_cache=False)
        print(f"Firestore Portfolios: {len(df)} rows")
        if not df.empty and "username" in df.columns:
            users = sorted(df["username"].astype(str).str.strip().unique().tolist())
            print("  usernames:", ", ".join(users) or "(empty)")
        if not df.empty and "portfolio_name" in df.columns:
            names = sorted(
                df["portfolio_name"].astype(str).str.strip().unique().tolist()
            )
            print("  portfolios:", ", ".join(n for n in names if n and n != "__PLACEHOLDER__")[:500])
        if df.empty:
            print(
                "\nFirestore is empty. Fix .env (service account), then:\n"
                "  python scripts/migrate_gsheets_to_firestore.py"
            )
    except Exception as e:
        print("ERROR:", e)
        print(
            "\nIf credentials mention apiKey: replace FIREBASE_CREDENTIALS_JSON with a "
            "service account key (see .env.example)."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
