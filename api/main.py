"""REST API for the Portfolio Manager mobile app."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from portfolio_core import GLOBAL_OVERVIEW_LABEL, PORTFOLIO_TYPE_GROWTH, filter_master_data_for_user

from api import dividends, portfolio_actions, services, stock_purchases
from api.sheets import read_portfolios

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv(override=True)

app = FastAPI(title="Portfolio Manager API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)
JWT_SECRET = os.getenv("COOKIE_KEY", "")
ADMIN_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")
TOKEN_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "168"))


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    name: str
    username: str


class HoldingInput(BaseModel):
    ticker: str
    current_value: float
    target_allocation: float = 0.0
    tolerance: float = 2.0
    expense_ratio: float = 0.0
    current_price: float = 0.0


class SavePortfolioRequest(BaseModel):
    holdings: list[HoldingInput]
    monthly_invest: float | None = None
    uninvested_cash: float | None = None
    safe_liquidity: float | None = None


class CalculateAllocationRequest(BaseModel):
    monthly_invest: float | None = None
    uninvested_cash: float | None = None
    safe_liquidity: float | None = None


class AddStockPurchaseRequest(BaseModel):
    ticker: str
    unit_price: float
    quantity: float
    sector: str = ""
    industry: str = ""
    country: str = ""
    currency: str = ""
    dividend_yield: float = 0.0


class DeleteStockUnitsRequest(BaseModel):
    unit_keys: list[str]


class UpdateStockMarketValuesRequest(BaseModel):
    market_values: dict[str, float]


class AddDividendRequest(BaseModel):
    date: str
    ticker: str
    amount: float


def _issue_token(username: str, name: str) -> str:
    if not JWT_SECRET:
        raise HTTPException(status_code=500, detail="COOKIE_KEY not configured")
    payload = {
        "sub": username,
        "name": name,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/login", response_model=LoginResponse)
def login(body: LoginRequest) -> LoginResponse:
    if not ADMIN_HASH:
        raise HTTPException(status_code=500, detail="ADMIN_PASSWORD_HASH not configured")
    if body.username != "admin":
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not _verify_password(body.password, ADMIN_HASH):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    name = "Admin User"
    token = _issue_token(body.username, name)
    return LoginResponse(access_token=token, name=name, username=body.username)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> dict[str, str]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if not JWT_SECRET:
        raise HTTPException(status_code=500, detail="COOKIE_KEY not configured")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"username": str(username), "name": str(payload.get("name", username))}


@app.get("/me")
def me(user: Annotated[dict[str, str], Depends(get_current_user)]) -> dict[str, str]:
    return user


def _load_master_data():
    try:
        return read_portfolios()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot load Firestore: {exc}",
        ) from exc


@app.get("/portfolios")
def list_portfolios(user: Annotated[dict[str, str], Depends(get_current_user)]) -> dict:
    master = _load_master_data()
    return services.build_home_payload(master, user["username"])


@app.get("/portfolios/{portfolio_name}")
def get_portfolio(
    portfolio_name: str,
    user: Annotated[dict[str, str], Depends(get_current_user)],
) -> dict:
    master = _load_master_data()
    return services.build_portfolio_summary(master, user["username"], portfolio_name)


@app.get("/portfolios/{portfolio_name}/allocation")
def get_allocation(
    portfolio_name: str,
    user: Annotated[dict[str, str], Depends(get_current_user)],
) -> dict:
    master = _load_master_data()
    summary = services.build_portfolio_summary(master, user["username"], portfolio_name)
    if summary["portfolio_type"] != PORTFOLIO_TYPE_GROWTH:
        raise HTTPException(status_code=400, detail="Allocation plan is only for Growth portfolios")
    return services.build_growth_allocation(master, user["username"], portfolio_name)


@app.put("/portfolios/{portfolio_name}")
def save_portfolio(
    portfolio_name: str,
    body: SavePortfolioRequest,
    user: Annotated[dict[str, str], Depends(get_current_user)],
) -> dict:
    if portfolio_name == GLOBAL_OVERVIEW_LABEL:
        raise HTTPException(status_code=400, detail="Cannot edit global overview")
    master = _load_master_data()
    summary = services.build_portfolio_summary(master, user["username"], portfolio_name)
    holdings = [h.model_dump() for h in body.holdings]
    portfolio_actions.save_portfolio(
        master,
        user["username"],
        portfolio_name,
        holdings=holdings,
        monthly_invest=body.monthly_invest,
        uninvested_cash=body.uninvested_cash,
        safe_liquidity=body.safe_liquidity,
        portfolio_type=summary["portfolio_type"],
    )
    return {"status": "ok", "message": "Portfolio saved"}


@app.post("/portfolios/{portfolio_name}/calculate-allocation")
def calculate_allocation(
    portfolio_name: str,
    user: Annotated[dict[str, str], Depends(get_current_user)],
    body: CalculateAllocationRequest | None = None,
) -> dict:
    master = _load_master_data()
    summary = services.build_portfolio_summary(master, user["username"], portfolio_name)
    opts = body or CalculateAllocationRequest()
    p_type = summary["portfolio_type"]
    if p_type == PORTFOLIO_TYPE_GROWTH:
        return portfolio_actions.calculate_growth_allocation(
            master,
            user["username"],
            portfolio_name,
            monthly_invest=opts.monthly_invest,
            uninvested_cash=opts.uninvested_cash,
            safe_liquidity=opts.safe_liquidity,
        )
    if p_type == "Kids":
        try:
            return portfolio_actions.calculate_kids_allocation(
                master,
                user["username"],
                portfolio_name,
                uninvested_cash=opts.uninvested_cash,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise HTTPException(
        status_code=400,
        detail="Allocation calculator is available for Growth and Kids portfolios.",
    )


@app.post("/portfolios/{portfolio_name}/log-investment")
def log_investment(
    portfolio_name: str,
    user: Annotated[dict[str, str], Depends(get_current_user)],
    body: CalculateAllocationRequest | None = None,
) -> dict:
    master = _load_master_data()
    summary = services.build_portfolio_summary(master, user["username"], portfolio_name)
    if summary["portfolio_type"] != PORTFOLIO_TYPE_GROWTH:
        raise HTTPException(status_code=400, detail="Investment log applies to Growth portfolios")
    opts = body or CalculateAllocationRequest()
    calc = portfolio_actions.calculate_growth_allocation(
        master,
        user["username"],
        portfolio_name,
        monthly_invest=opts.monthly_invest,
        uninvested_cash=opts.uninvested_cash,
        safe_liquidity=opts.safe_liquidity,
    )
    return portfolio_actions.log_growth_investment(
        master, user["username"], portfolio_name, calc=calc
    )


def _require_stocks_portfolio(master, username: str, portfolio_name: str) -> None:
    if services.portfolio_type_for_name(master, username, portfolio_name) != "Stocks":
        raise HTTPException(
            status_code=400, detail="This endpoint is only for Stocks portfolios"
        )


@app.get("/portfolios/{portfolio_name}/stock-purchases")
def get_stock_purchases(
    portfolio_name: str,
    user: Annotated[dict[str, str], Depends(get_current_user)],
) -> dict:
    master = _load_master_data()
    _require_stocks_portfolio(master, user["username"], portfolio_name)
    return stock_purchases.build_stock_purchases_payload(
        master, user["username"], portfolio_name
    )


@app.post("/portfolios/{portfolio_name}/stock-purchases")
def add_stock_purchase(
    portfolio_name: str,
    body: AddStockPurchaseRequest,
    user: Annotated[dict[str, str], Depends(get_current_user)],
) -> dict:
    master = _load_master_data()
    _require_stocks_portfolio(master, user["username"], portfolio_name)
    try:
        return stock_purchases.add_purchase(
            master,
            user["username"],
            portfolio_name,
            ticker=body.ticker,
            unit_price=body.unit_price,
            quantity=body.quantity,
            sector=body.sector,
            industry=body.industry,
            country=body.country,
            currency=body.currency,
            dividend_yield=body.dividend_yield,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/portfolios/{portfolio_name}/stock-purchases/units/{unit_key}")
def delete_stock_unit(
    portfolio_name: str,
    unit_key: str,
    user: Annotated[dict[str, str], Depends(get_current_user)],
) -> dict:
    master = _load_master_data()
    _require_stocks_portfolio(master, user["username"], portfolio_name)
    try:
        return stock_purchases.delete_unit(
            master, user["username"], portfolio_name, unit_key
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.patch("/portfolios/{portfolio_name}/stock-market-values")
def patch_stock_market_values(
    portfolio_name: str,
    body: UpdateStockMarketValuesRequest,
    user: Annotated[dict[str, str], Depends(get_current_user)],
) -> dict:
    master = _load_master_data()
    _require_stocks_portfolio(master, user["username"], portfolio_name)
    if not body.market_values:
        raise HTTPException(status_code=400, detail="No market values provided")
    try:
        return stock_purchases.update_market_values(
            master,
            user["username"],
            portfolio_name,
            body.market_values,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/portfolios/{portfolio_name}/stock-purchases/delete-units")
def delete_stock_units(
    portfolio_name: str,
    body: DeleteStockUnitsRequest,
    user: Annotated[dict[str, str], Depends(get_current_user)],
) -> dict:
    master = _load_master_data()
    _require_stocks_portfolio(master, user["username"], portfolio_name)
    try:
        return stock_purchases.delete_units(
            master, user["username"], portfolio_name, body.unit_keys
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/portfolios/{portfolio_name}/charts")
def get_charts(
    portfolio_name: str,
    user: Annotated[dict[str, str], Depends(get_current_user)],
) -> dict:
    master = _load_master_data()
    if portfolio_name == GLOBAL_OVERVIEW_LABEL:
        summary = services.build_portfolio_summary(
            master, user["username"], portfolio_name
        )
        pie = [
            {"name": b["name"], "value": b["total_value"]}
            for b in summary.get("breakdown", [])
            if b.get("total_value", 0) > 0
        ]
        return {
            "time_series": [],
            "holdings_pie": pie,
            "total_value": summary["total_value"],
            "total_invested": 0,
            "distributions": {"by_portfolio": pie},
        }
    return portfolio_actions.build_chart_payload(
        master, user["username"], portfolio_name
    )


@app.get("/portfolios/{portfolio_name}/dividends")
def get_dividends(
    portfolio_name: str,
    user: Annotated[dict[str, str], Depends(get_current_user)],
) -> dict:
    master = _load_master_data()
    _require_stocks_portfolio(master, user["username"], portfolio_name)
    return dividends.dividend_summary(user["username"], portfolio_name)


@app.post("/portfolios/{portfolio_name}/dividends")
def post_dividend(
    portfolio_name: str,
    body: AddDividendRequest,
    user: Annotated[dict[str, str], Depends(get_current_user)],
) -> dict:
    master = _load_master_data()
    _require_stocks_portfolio(master, user["username"], portfolio_name)
    try:
        return dividends.add_dividend(
            user["username"],
            portfolio_name,
            date=body.date,
            ticker=body.ticker,
            amount=body.amount,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
