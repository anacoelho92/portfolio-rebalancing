"""Legacy Google Sheets access — used only by scripts/migrate_gsheets_to_firestore.py."""

from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable, TypeVar

import gspread
from gspread.exceptions import APIError
import pandas as pd
from google.oauth2.service_account import Credentials

from portfolio_core import (
    PORTFOLIOS_REQUIRED_COLUMNS,
    empty_portfolios_dataframe,
    migrate_growth_portfolio_metadata,
)

NUMERIC_PORTFOLIO_COLS = [
    "current_value",
    "target_allocation",
    "tolerance",
    "expense_ratio",
    "portfolio_monthly_invest",
    "portfolio_buffett_index",
    "quantity",
    "average_price",
    "dividend_yield",
    "portfolio_uninvested_cash",
    "current_price",
    "portfolio_safe_liquidity",
    "portfolio_uninvested_reinvested",
]


def parse_locale_number(value: Any) -> float:
    """
    Parse numbers from Google Sheets cells (often European: 7140,2 not 71402).
    get_all_records() mis-parses comma decimals when the API returns floats.
    """
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        if pd.isna(value):
            return 0.0
        return float(value)
    s = str(value).strip().replace("\u00a0", "").replace(" ", "").replace("€", "")
    if not s or s.lower() in ("nan", "none", "nat"):
        return 0.0
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            s = f"{parts[0]}.{parts[1]}"
        else:
            s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _dataframe_from_worksheet(worksheet) -> pd.DataFrame:
    """Read sheet as raw strings, then parse locale numbers (avoids gspread float bugs)."""
    rows = worksheet.get_all_values()
    if not rows:
        return pd.DataFrame()
    header = [str(h).strip() for h in rows[0]]
    records = []
    for row in rows[1:]:
        if not any(str(c).strip() for c in row):
            continue
        padded = list(row) + [""] * max(0, len(header) - len(row))
        records.append(dict(zip(header, padded[: len(header)])))
    return pd.DataFrame(records)


def _apply_numeric_parsing(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    for col in columns:
        if col in out.columns:
            out[col] = out[col].apply(parse_locale_number)
    return out

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_ROOT = Path(__file__).resolve().parent.parent
_SECRETS_PATH = _ROOT / ".streamlit" / "secrets.toml"


def _parse_toml_bytes(data: bytes) -> dict[str, Any]:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]
    try:
        return tomllib.loads(data)
    except TypeError:
        return tomllib.loads(data.decode("utf-8"))


def _gsheets_section_from_toml() -> dict[str, Any] | None:
    if _SECRETS_PATH.is_file():
        return _parse_toml_bytes(_SECRETS_PATH.read_bytes()).get("connections", {}).get(
            "gsheets"
        )
    raw = os.getenv("SECRETS_TOML")
    if raw:
        return _parse_toml_bytes(raw.encode("utf-8")).get("connections", {}).get("gsheets")
    return None


def _credentials_info() -> dict[str, Any]:
    raw = os.getenv("GSHEETS_CREDENTIALS_JSON")
    if raw:
        return json.loads(raw)

    section = _gsheets_section_from_toml()
    if section:
        private_key = str(section.get("private_key", "")).replace("\\n", "\n")
        return {
            "type": section.get("type", "service_account"),
            "project_id": section.get("project_id", ""),
            "private_key_id": section.get("private_key_id", ""),
            "private_key": private_key,
            "client_email": section.get("client_email", ""),
            "client_id": str(section.get("client_id", "")),
            "auth_uri": section.get(
                "auth_uri", "https://accounts.google.com/o/oauth2/auth"
            ),
            "token_uri": section.get(
                "token_uri", "https://oauth2.googleapis.com/token"
            ),
            "auth_provider_x509_cert_url": section.get(
                "auth_provider_x509_cert_url",
                "https://www.googleapis.com/oauth2/v1/certs",
            ),
            "client_x509_cert_url": section.get("client_x509_cert_url", ""),
        }

    private_key = (os.getenv("GSHEETS_PRIVATE_KEY") or "").replace("\\n", "\n")
    return {
        "type": os.getenv("GSHEETS_TYPE", "service_account"),
        "project_id": os.getenv("GSHEETS_PROJECT_ID", ""),
        "private_key_id": os.getenv("GSHEETS_PRIVATE_KEY_ID", ""),
        "private_key": private_key,
        "client_email": os.getenv("GSHEETS_CLIENT_EMAIL", ""),
        "client_id": os.getenv("GSHEETS_CLIENT_ID", ""),
        "auth_uri": os.getenv("GSHEETS_AUTH_URI", "https://accounts.google.com/o/oauth2/auth"),
        "token_uri": os.getenv("GSHEETS_TOKEN_URI", "https://oauth2.googleapis.com/token"),
        "auth_provider_x509_cert_url": os.getenv(
            "GSHEETS_AUTH_PROVIDER_CERT_URL",
            "https://www.googleapis.com/oauth2/v1/certs",
        ),
        "client_x509_cert_url": os.getenv("GSHEETS_CLIENT_X509_CERT_URL", ""),
    }


def _spreadsheet_url() -> str:
    url = (
        os.getenv("GSHEETS_SPREADSHEET_URL")
        or os.getenv("GSHEETS_URL")
        or os.getenv("GSHEETS_SPREADSHEET")
        or ""
    ).strip()
    if url:
        return url
    section = _gsheets_section_from_toml()
    if section and section.get("spreadsheet"):
        return str(section["spreadsheet"]).strip()
    raise RuntimeError(
        "Google Sheet URL not configured. Set GSHEETS_URL or GSHEETS_SPREADSHEET_URL, "
        "or add [connections.gsheets] spreadsheet in .streamlit/secrets.toml."
    )


def _spreadsheet_key() -> str:
    url = _spreadsheet_url()
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
    if match:
        return match.group(1)
    if "/" not in url:
        return url
    raise RuntimeError(f"Invalid Google Sheet URL: {url}")


def _validate_credentials(info: dict[str, Any]) -> None:
    if not info.get("client_email") or not info.get("private_key"):
        raise RuntimeError(
            "Google Sheets credentials missing. Use .streamlit/secrets.toml "
            "(same as Streamlit), GSHEETS_CREDENTIALS_JSON, or GSHEETS_CLIENT_EMAIL + "
            "GSHEETS_PRIVATE_KEY."
        )
    if "BEGIN PRIVATE KEY" not in str(info["private_key"]):
        raise RuntimeError(
            "GSHEETS_PRIVATE_KEY is invalid or empty. Copy private_key from "
            ".streamlit/secrets.toml [connections.gsheets]."
        )


_gs_client: gspread.Client | None = None
_spreadsheet: gspread.Spreadsheet | None = None
_worksheet_cache: dict[str, gspread.Worksheet] = {}
_df_cache: dict[str, pd.DataFrame] = {}
_df_cache_ts: dict[str, float] = {}
_CACHE_TTL_SEC = 90
_load_locks: dict[str, threading.Lock] = {}

T = TypeVar("T")


def _invalidate_df_cache(*keys: str) -> None:
    if keys:
        for key in keys:
            _df_cache.pop(key, None)
            _df_cache_ts.pop(key, None)
    else:
        _df_cache.clear()
        _df_cache_ts.clear()


def _retry_gs(call: Callable[[], T], *, attempts: int = 4) -> T:
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return call()
        except APIError as exc:
            last_exc = exc
            code = getattr(getattr(exc, "response", None), "status_code", None)
            if code == 429 and attempt < attempts - 1:
                time.sleep(min(2**attempt, 8))
                continue
            raise
    if last_exc:
        raise last_exc
    raise RuntimeError("Google Sheets request failed")


def _get_gs_client() -> gspread.Client:
    global _gs_client
    if _gs_client is not None:
        return _gs_client
    info = _credentials_info()
    _validate_credentials(info)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    _gs_client = gspread.authorize(creds)
    return _gs_client


def _get_spreadsheet() -> gspread.Spreadsheet:
    global _spreadsheet
    if _spreadsheet is None:
        _spreadsheet = _retry_gs(
            lambda: _get_gs_client().open_by_key(_spreadsheet_key())
        )
    return _spreadsheet


def _get_worksheet(worksheet_name: str) -> gspread.Worksheet:
    if worksheet_name in _worksheet_cache:
        return _worksheet_cache[worksheet_name]

    def _open() -> gspread.Worksheet:
        sheet = _get_spreadsheet()
        try:
            return sheet.worksheet(worksheet_name)
        except gspread.WorksheetNotFound:
            return sheet.add_worksheet(
                title=worksheet_name,
                rows=10,
                cols=5,
            )

    ws = _retry_gs(_open)
    _worksheet_cache[worksheet_name] = ws
    return ws


def _cached_df(cache_key: str, loader: Callable[[], pd.DataFrame]) -> pd.DataFrame:
    now = time.monotonic()
    if cache_key in _df_cache and now - _df_cache_ts.get(cache_key, 0.0) < _CACHE_TTL_SEC:
        return _df_cache[cache_key].copy()

    lock = _load_locks.setdefault(cache_key, threading.Lock())
    with lock:
        now = time.monotonic()
        if cache_key in _df_cache and now - _df_cache_ts.get(cache_key, 0.0) < _CACHE_TTL_SEC:
            return _df_cache[cache_key].copy()
        df = loader()
        _df_cache[cache_key] = df
        _df_cache_ts[cache_key] = now
        return df.copy()


def _normalize_portfolios(raw: pd.DataFrame) -> pd.DataFrame:
    if raw is None or raw.empty:
        return empty_portfolios_dataframe()
    for col in PORTFOLIOS_REQUIRED_COLUMNS:
        if col not in raw.columns:
            if col == "portfolio_monthly_invest":
                raw[col] = 1000.0
            elif col == "portfolio_use_indicators":
                raw[col] = False
            elif col == "portfolio_buffett_index":
                raw[col] = 195.0
            elif col == "portfolio_type":
                raw[col] = "Other"
            elif col in (
                "current_value",
                "target_allocation",
                "tolerance",
                "expense_ratio",
                "quantity",
                "average_price",
                "dividend_yield",
                "current_price",
                "portfolio_uninvested_cash",
                "portfolio_safe_liquidity",
                "portfolio_uninvested_reinvested",
            ):
                raw[col] = 0.0
            elif col == "investor_birth_date":
                raw[col] = "1992-01-01"
            else:
                raw[col] = ""
    raw = raw.astype(
        {
            "username": "str",
            "stock_name": "str",
            "current_value": "float",
            "target_allocation": "float",
            "expense_ratio": "float",
            "portfolio_name": "str",
            "current_price": "float",
        }
    )
    raw["portfolio_name"] = raw["portfolio_name"].fillna("Default")
    raw["username"] = raw["username"].fillna("unknown")
    return migrate_growth_portfolio_metadata(raw)


def read_portfolios(*, use_cache: bool = True) -> pd.DataFrame:
    def _load() -> pd.DataFrame:
        worksheet = _get_worksheet("Portfolios")
        raw = _dataframe_from_worksheet(worksheet)
        raw = _apply_numeric_parsing(raw, NUMERIC_PORTFOLIO_COLS)
        return _normalize_portfolios(raw)

    if use_cache:
        return _cached_df("portfolios", _load)
    return _load()


def read_investment_log() -> pd.DataFrame:
    try:
        def _load() -> pd.DataFrame:
            worksheet = _get_worksheet("InvestmentLog")
            raw = _dataframe_from_worksheet(worksheet)
            log_numeric = [
                "Current Value",
                "Current %",
                "Target %",
                "Target Value",
                "Investment",
                "New Value",
                "New %",
            ]
            return _apply_numeric_parsing(raw, log_numeric)

        return _cached_df("investment_log", _load)
    except Exception:
        return pd.DataFrame()


def write_worksheet(worksheet_name: str, df: pd.DataFrame) -> None:
    """Replace worksheet contents with dataframe (same as Streamlit conn.update)."""
    from gspread_dataframe import set_with_dataframe

    ws = _get_worksheet(worksheet_name)

    def _write() -> None:
        ws.clear()
        if df.empty:
            ws.update([list(df.columns)])
            return
        set_with_dataframe(
            ws, df, include_index=False, include_column_header=True, resize=True
        )

    _retry_gs(_write)
    if worksheet_name == "Portfolios":
        _invalidate_df_cache("portfolios")
    elif worksheet_name == "StockPurchases":
        _invalidate_df_cache("stock_purchases")
    elif worksheet_name == "InvestmentLog":
        _invalidate_df_cache("investment_log")
    elif worksheet_name == "Dividends":
        _invalidate_df_cache("dividends")


def write_portfolios(df: pd.DataFrame) -> pd.DataFrame:
    normalized = _normalize_portfolios(df)
    write_worksheet("Portfolios", normalized)
    return normalized


def write_stock_purchases(df: pd.DataFrame) -> None:
    write_worksheet("StockPurchases", df)


def read_stock_purchases(*, use_cache: bool = True) -> pd.DataFrame:
    try:
        def _load() -> pd.DataFrame:
            worksheet = _get_worksheet("StockPurchases")
            raw = _dataframe_from_worksheet(worksheet)
            return _apply_numeric_parsing(
                raw,
                ["unit_price", "quantity", "dividend_yield", "dps"],
            )

        if use_cache:
            return _cached_df("stock_purchases", _load)
        return _load()
    except Exception:
        return pd.DataFrame()


def read_dividends(*, use_cache: bool = True) -> pd.DataFrame:
    try:
        def _load() -> pd.DataFrame:
            worksheet = _get_worksheet("Dividends")
            raw = _dataframe_from_worksheet(worksheet)
            df = _apply_numeric_parsing(raw, ["amount"])
            if df.empty:
                return df
            return df.dropna(subset=["date"])

        if use_cache:
            return _cached_df("dividends", _load)
        return _load()
    except Exception:
        return pd.DataFrame()
