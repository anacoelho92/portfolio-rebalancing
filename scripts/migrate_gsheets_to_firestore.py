#!/usr/bin/env python3
"""One-time copy from Google Sheets worksheets into Firestore collections."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
load_dotenv(override=True)

from api import gsheets_legacy, sheets

WORKSHEETS = [
    ("Portfolios", gsheets_legacy.read_portfolios),
    ("StockPurchases", lambda: gsheets_legacy.read_stock_purchases(use_cache=False)),
    ("Dividends", lambda: gsheets_legacy.read_dividends(use_cache=False)),
    ("InvestmentLog", gsheets_legacy.read_investment_log),
]


def main() -> None:
    print("Reading from Google Sheets…")
    for name, loader in WORKSHEETS:
        df = loader()
        print(f"  {name}: {len(df)} rows")
        sheets.write_worksheet(name, df)
    print("Done. Firestore collections:", ", ".join(sheets.WORKSHEETS))


if __name__ == "__main__":
    main()
