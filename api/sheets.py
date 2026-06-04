"""Firestore persistence (replaces Google Sheets worksheets)."""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, TypeVar

import firebase_admin
import pandas as pd
from dotenv import load_dotenv
from firebase_admin import credentials, firestore
from google.api_core import exceptions as google_exceptions

from portfolio_core import (
    PORTFOLIOS_REQUIRED_COLUMNS,
    empty_portfolios_dataframe,
    migrate_growth_portfolio_metadata,
)

# Firestore collection names (one collection per former worksheet tab).
WORKSHEETS = ("Portfolios", "StockPurchases", "Dividends", "InvestmentLog")
_SHEET_DOC_ID = "data"

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

_ROOT = Path(__file__).resolve().parent.parent
_SECRETS_PATH = _ROOT / ".streamlit" / "secrets.toml"

load_dotenv(_ROOT / ".env")
load_dotenv(override=True)

_df_cache: dict[str, pd.DataFrame] = {}
_df_cache_ts: dict[str, float] = {}
_CACHE_TTL_SEC = 90
_load_locks: dict[str, threading.Lock] = {}

T = TypeVar("T")


def parse_locale_number(value: Any) -> float:
    """Parse numbers stored as strings (European decimals) or native types."""
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


def _apply_numeric_parsing(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    for col in columns:
        if col in out.columns:
            out[col] = out[col].apply(parse_locale_number)
    return out


def _parse_toml_bytes(data: bytes) -> dict[str, Any]:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]
    try:
        return tomllib.loads(data)
    except TypeError:
        return tomllib.loads(data.decode("utf-8"))


def _firebase_section_from_toml() -> dict[str, Any] | None:
    if _SECRETS_PATH.is_file():
        return _parse_toml_bytes(_SECRETS_PATH.read_bytes()).get("firebase")
    raw = os.getenv("SECRETS_TOML")
    if raw:
        return _parse_toml_bytes(raw.encode("utf-8")).get("firebase")
    return None


def _normalize_service_account_info(info: dict[str, Any]) -> dict[str, Any]:
    """Accept standard service account JSON; reject Firebase Web app config."""
    if info.get("apiKey") and not info.get("private_key"):
        raise RuntimeError(
            "FIREBASE_CREDENTIALS_JSON looks like a Firebase Web app config (apiKey, projectId). "
            "Use a service account key instead: Firebase Console → Project settings → "
            "Service accounts → Generate new private key."
        )
    if info.get("projectId") and not info.get("project_id"):
        info = {**info, "project_id": info["projectId"]}
    return info


def _credentials_info() -> dict[str, Any]:
    raw = os.getenv("FIREBASE_CREDENTIALS_JSON")
    if raw:
        return _normalize_service_account_info(json.loads(raw))

    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if cred_path and Path(cred_path).is_file():
        return _normalize_service_account_info(
            json.loads(Path(cred_path).read_text(encoding="utf-8"))
        )

    section = _firebase_section_from_toml()
    if section and section.get("credentials_json"):
        return json.loads(section["credentials_json"])
    if section and section.get("private_key"):
        return {
            "type": section.get("type", "service_account"),
            "project_id": section.get("project_id", ""),
            "private_key_id": section.get("private_key_id", ""),
            "private_key": str(section.get("private_key", "")).replace("\\n", "\n"),
            "client_email": section.get("client_email", ""),
            "client_id": str(section.get("client_id", "")),
            "token_uri": section.get(
                "token_uri", "https://oauth2.googleapis.com/token"
            ),
        }

    # One-time migration: same service account JSON as former Google Sheets setup.
    legacy = os.getenv("GSHEETS_CREDENTIALS_JSON")
    if legacy:
        return json.loads(legacy)

    if _SECRETS_PATH.is_file():
        gs = _parse_toml_bytes(_SECRETS_PATH.read_bytes()).get("connections", {}).get(
            "gsheets"
        )
        if gs:
            return {
                "type": gs.get("type", "service_account"),
                "project_id": gs.get("project_id", ""),
                "private_key_id": gs.get("private_key_id", ""),
                "private_key": str(gs.get("private_key", "")).replace("\\n", "\n"),
                "client_email": gs.get("client_email", ""),
                "client_id": str(gs.get("client_id", "")),
                "token_uri": gs.get(
                    "token_uri", "https://oauth2.googleapis.com/token"
                ),
            }

    raise RuntimeError(
        "Firebase credentials missing. Set FIREBASE_CREDENTIALS_JSON, "
        "GOOGLE_APPLICATION_CREDENTIALS, or [firebase] in .streamlit/secrets.toml."
    )


def _project_id() -> str:
    explicit = (
        os.getenv("FIREBASE_PROJECT_ID")
        or os.getenv("GCLOUD_PROJECT")
        or ""
    ).strip()
    if explicit:
        return explicit
    section = _firebase_section_from_toml()
    if section and section.get("project_id"):
        return str(section["project_id"]).strip()
    info = _credentials_info()
    pid = str(info.get("project_id") or info.get("projectId") or "").strip()
    if pid:
        return pid
    raise RuntimeError(
        "Firebase project id missing. Set FIREBASE_PROJECT_ID or include project_id "
        "in the service account JSON."
    )


def _serialize_cell(value: Any) -> Any:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, AttributeError):
            pass
    return value


def _df_to_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    rows: list[dict[str, Any]] = []
    for record in df.to_dict(orient="records"):
        rows.append({k: _serialize_cell(v) for k, v in record.items()})
    return rows


def _rows_to_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _get_firestore_client() -> firestore.Client:
    if not firebase_admin._apps:
        info = _credentials_info()
        if not info.get("client_email") or not info.get("private_key"):
            raise RuntimeError("Firebase service account JSON is incomplete.")
        cred = credentials.Certificate(info)
        firebase_admin.initialize_app(cred, {"projectId": _project_id()})
    return firestore.client()


def _sheet_ref(worksheet_name: str):
    if worksheet_name not in WORKSHEETS:
        raise ValueError(f"Unknown worksheet: {worksheet_name}")
    return _get_firestore_client().collection(worksheet_name).document(_SHEET_DOC_ID)


def invalidate_cache(*keys: str) -> None:
    _invalidate_df_cache(*keys)


def _invalidate_df_cache(*keys: str) -> None:
    if keys:
        for key in keys:
            _df_cache.pop(key, None)
            _df_cache_ts.pop(key, None)
    else:
        _df_cache.clear()
        _df_cache_ts.clear()


def _retry_firestore(call: Callable[[], T], *, attempts: int = 4) -> T:
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return call()
        except (
            google_exceptions.ResourceExhausted,
            google_exceptions.ServiceUnavailable,
            google_exceptions.DeadlineExceeded,
        ) as exc:
            last_exc = exc
            if attempt < attempts - 1:
                time.sleep(min(2**attempt, 8))
                continue
            raise
    if last_exc:
        raise last_exc
    raise RuntimeError("Firestore request failed")


def _read_rows(worksheet_name: str) -> list[dict[str, Any]]:
    def _load() -> list[dict[str, Any]]:
        snap = _retry_firestore(lambda: _sheet_ref(worksheet_name).get())
        if not snap.exists:
            return []
        data = snap.to_dict() or {}
        rows = data.get("rows")
        return list(rows) if isinstance(rows, list) else []

    return _load()


def _write_rows(worksheet_name: str, rows: list[dict[str, Any]]) -> None:
    def _save() -> None:
        _sheet_ref(worksheet_name).set(
            {
                "rows": rows,
                "updated_at": firestore.SERVER_TIMESTAMP,
            }
        )

    _retry_firestore(_save)


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
        raw = _rows_to_dataframe(_read_rows("Portfolios"))
        raw = _apply_numeric_parsing(raw, NUMERIC_PORTFOLIO_COLS)
        return _normalize_portfolios(raw)

    if use_cache:
        return _cached_df("portfolios", _load)
    return _load()


def read_investment_log() -> pd.DataFrame:
    try:
        def _load() -> pd.DataFrame:
            raw = _rows_to_dataframe(_read_rows("InvestmentLog"))
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
    """Replace worksheet contents with dataframe."""
    rows = _df_to_rows(df)
    if df.empty and rows:
        rows = []
    _write_rows(worksheet_name, rows)
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
            raw = _rows_to_dataframe(_read_rows("StockPurchases"))
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
            raw = _rows_to_dataframe(_read_rows("Dividends"))
            df = _apply_numeric_parsing(raw, ["amount"])
            if df.empty:
                return df
            return df.dropna(subset=["date"])

        if use_cache:
            return _cached_df("dividends", _load)
        return _load()
    except Exception:
        return pd.DataFrame()
