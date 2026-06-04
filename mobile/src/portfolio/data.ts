import type { Holding } from "../types";
import {
  calculateInvestorAge,
  DEFAULT_INVESTOR_BIRTH_DATE,
  EXCLUDED_GD_TICKERS,
  filterByPortfolio,
  GROWTH_DIVIDENDS_TICKERS,
  growthTargetsByTicker,
  kidsTargetsFromBirth,
  normalizePortfolioType,
  safeFloat,
  type MasterRow,
  getTolerance,
  GD_TICKER_MAP,
  PORTFOLIO_TYPE_GROWTH,
} from "./core";

function growthTargetsForAge(age: number): Record<string, number> {
  return growthTargetsByTicker(age);
}

export function portfolioMetadata(rows: MasterRow[]) {
  if (!rows.length) {
    return {
      portfolio_type: PORTFOLIO_TYPE_GROWTH,
      monthly_invest: 1000,
      uninvested_cash: 0,
      safe_liquidity: 0,
      investor_birth_date: DEFAULT_INVESTOR_BIRTH_DATE,
      portfolio_birth_date: "",
    };
  }
  const row = rows[0]!;
  return {
    portfolio_type: normalizePortfolioType(String(row.portfolio_type ?? "Other")),
    monthly_invest: safeFloat(row.portfolio_monthly_invest, 1000),
    uninvested_cash: safeFloat(row.portfolio_uninvested_cash),
    safe_liquidity: safeFloat(row.portfolio_safe_liquidity),
    investor_birth_date: String(row.investor_birth_date || DEFAULT_INVESTOR_BIRTH_DATE),
    portfolio_birth_date: String(row.portfolio_birth_date ?? ""),
  };
}

export function stocksFromRows(rows: MasterRow[]) {
  return rows
    .filter((r) => String(r.stock_name) !== "__PLACEHOLDER__")
    .map((r) => ({
      name: String(r.stock_name),
      current_value: safeFloat(r.current_value),
      target_allocation: safeFloat(r.target_allocation),
      tolerance: safeFloat(r.tolerance, 2),
      expense_ratio: safeFloat(r.expense_ratio),
      sector: String(r.sector ?? ""),
      industry: String(r.industry ?? ""),
      quantity: safeFloat(r.quantity),
      average_price: safeFloat(r.average_price),
    }));
}

export function growthStocksFromRows(rows: MasterRow[], investorBirth: string) {
  const filtered = rows.filter((r) => String(r.stock_name) !== "__PLACEHOLDER__");
  const aggregated: Record<
    string,
    {
      name: string;
      current_value: number;
      target_allocation: number;
      tolerance: number;
      expense_ratio: number;
      sector: string;
      industry: string;
    }
  > = {};

  for (const row of filtered) {
    const raw = String(row.stock_name);
    const mapped = GD_TICKER_MAP[raw] ?? raw;
    if (EXCLUDED_GD_TICKERS.has(mapped.toUpperCase())) continue;
    if (!aggregated[mapped]) {
      aggregated[mapped] = {
        name: mapped,
        current_value: 0,
        target_allocation: 0,
        tolerance: getTolerance(mapped),
        expense_ratio: safeFloat(row.expense_ratio),
        sector: String(row.sector ?? ""),
        industry: String(row.industry ?? ""),
      };
    }
    const rec = aggregated[mapped]!;
    rec.current_value += safeFloat(row.current_value);
    if (rec.expense_ratio === 0 && safeFloat(row.expense_ratio) > 0) {
      rec.expense_ratio = safeFloat(row.expense_ratio);
    }
  }

  let stocks = Object.values(aggregated).filter(
    (s) => !EXCLUDED_GD_TICKERS.has(s.name.toUpperCase())
  );
  const existing = new Set(stocks.map((s) => s.name));
  for (const ticker of GROWTH_DIVIDENDS_TICKERS) {
    if (!existing.has(ticker)) {
      stocks.push({
        name: ticker,
        current_value: 0,
        target_allocation: 0,
        tolerance: getTolerance(ticker),
        expense_ratio: 0,
        sector: "",
        industry: "",
      });
    }
  }

  const age = calculateInvestorAge(investorBirth);
  let unifiedTargets: Record<string, number> = {};
  unifiedTargets = growthTargetsForAge(age);

  for (const stock of stocks) {
    if (unifiedTargets[stock.name] != null) {
      stock.target_allocation = unifiedTargets[stock.name]!;
      stock.tolerance = getTolerance(stock.name);
    }
  }

  const order = ["SPYL.DE", "IXUA.DE", "VFEA.DE", "EGLN.UK"];
  stocks.sort(
    (a, b) =>
      (order.indexOf(a.name) === -1 ? 99 : order.indexOf(a.name)) -
      (order.indexOf(b.name) === -1 ? 99 : order.indexOf(b.name))
  );
  return stocks;
}

export function kidsApplyTargets(stocks: StockRow[], birth: string) {
  const targets = kidsTargetsFromBirth(birth);
  if (!targets) return stocks;
  return stocks.map((s) => {
    const key = s.name.toUpperCase();
    if (targets[key] != null) return { ...s, target_allocation: targets[key]! };
    return s;
  });
}

export type StockRow = {
  name: string;
  current_value: number;
  target_allocation: number;
  tolerance: number;
  expense_ratio: number;
  sector: string;
  industry: string;
  quantity?: number;
  average_price?: number;
  total_invested?: number;
  dividend_yield?: number;
};

export function stocksToHoldings(stocks: StockRow[]): Holding[] {
  return stocks.map((s) => ({
    ticker: s.name,
    current_value: Math.round(s.current_value * 100) / 100,
    target_allocation: Math.round(s.target_allocation * 100) / 100,
    tolerance: Math.round((s.tolerance ?? 2) * 100) / 100,
    expense_ratio: Math.round(s.expense_ratio * 10000) / 10000,
  }));
}

export function portfolioTotal(
  stocks: { current_value: number }[],
  _type: string
): number {
  return Math.round(stocks.reduce((s, x) => s + x.current_value, 0) * 100) / 100;
}

export function assignGlobalLabel(row: MasterRow): string {
  const ticker = String(row.stock_name ?? "").toUpperCase();
  const pType = normalizePortfolioType(String(row.portfolio_type ?? ""));
  const pName = String(row.portfolio_name ?? "").trim();
  if (["YCSH.DE", "PRAB.DE", "IBTE.UK"].includes(ticker)) return pName;
  if (["EGLN.UK", "EGNL.UK"].includes(ticker)) return "Gold";
  if (pType === "Kids") return pName;
  if (pType === PORTFOLIO_TYPE_GROWTH || pName.toLowerCase().includes("growth")) {
    if (["SPYL.DE", "IXUA.DE", "VFEA.DE"].includes(ticker)) return "Growth";
    if (["WTEQ.DE", "VDIV.DE", "EDP.PT", "JMT.PT"].includes(ticker)) return "Dividends";
  }
  return pName;
}

export function globalBreakdown(userRows: MasterRow[]) {
  const valid = userRows.filter((r) => String(r.stock_name) !== "__PLACEHOLDER__");
  const sums: Record<string, number> = {};
  for (const row of valid) {
    const label = assignGlobalLabel(row);
    sums[label] = (sums[label] ?? 0) + safeFloat(row.current_value);
  }
  return Object.entries(sums)
    .filter(([, v]) => v > 0)
    .map(([name, total_value]) => ({
      name,
      total_value: Math.round(total_value * 100) / 100,
      portfolio_type: name,
    }));
}

export function globalTotal(userRows: MasterRow[]) {
  return globalBreakdown(userRows).reduce((s, b) => s + b.total_value, 0);
}

export { filterByPortfolio };
