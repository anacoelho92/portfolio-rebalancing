import type { Holding, PortfolioDetail } from "../types";
import {
  filterByPortfolio,
  filterForUser,
  GLOBAL_OVERVIEW_LABEL,
  PORTFOLIO_TYPE_GROWTH,
  type MasterRow,
} from "./core";
import {
  globalBreakdown,
  globalTotal,
  growthStocksFromRows,
  kidsApplyTargets,
  portfolioMetadata,
  portfolioTotal,
  stocksFromRows,
  stocksToHoldings,
  type StockRow,
} from "./data";
import { buildStocksHoldings } from "./stocksHoldings";

export function portfolioNames(rows: MasterRow[], username: string): string[] {
  const user = filterForUser(rows, username);
  return [
    ...new Set(
      user
        .map((r) => String(r.portfolio_name ?? "").trim())
        .filter((n) => n && n !== "__PLACEHOLDER__")
    ),
  ].sort();
}

export function buildHomePayload(rows: MasterRow[], username: string) {
  const userRows = filterForUser(rows, username);
  const names = portfolioNames(rows, username);
  const total = globalTotal(userRows);
  const overview: PortfolioDetail = {
    name: GLOBAL_OVERVIEW_LABEL,
    portfolio_type: "Overview",
    total_value: Math.round(total * 100) / 100,
    holdings: [],
    breakdown: globalBreakdown(userRows),
  };
  const items = [
    {
      name: GLOBAL_OVERVIEW_LABEL,
      portfolio_type: "Overview",
      total_value: overview.total_value,
    },
  ];
  for (const name of names) {
    const pRows = filterByPortfolio(userRows, name);
    const meta = portfolioMetadata(pRows);
    let stocks: StockRow[] =
      meta.portfolio_type === PORTFOLIO_TYPE_GROWTH
        ? growthStocksFromRows(pRows, meta.investor_birth_date)
        : stocksFromRows(pRows);
    if (meta.portfolio_type === "Kids" && meta.portfolio_birth_date) {
      stocks = kidsApplyTargets(stocks, meta.portfolio_birth_date);
    }
    const value = portfolioTotal(stocks, meta.portfolio_type);
    items.push({
      name,
      portfolio_type: meta.portfolio_type,
      total_value: value,
    });
  }
  return { total_value: Math.round(total * 100) / 100, portfolios: items, overview };
}

export async function buildPortfolioSummary(
  master: MasterRow[],
  username: string,
  portfolioName: string,
  purchases: MasterRow[],
  dividends: MasterRow[],
  logRows: MasterRow[]
): Promise<PortfolioDetail> {
  const userRows = filterForUser(master, username);
  if (portfolioName === GLOBAL_OVERVIEW_LABEL) {
    return {
      name: GLOBAL_OVERVIEW_LABEL,
      portfolio_type: "Overview",
      total_value: globalTotal(userRows),
      holdings: [],
      breakdown: globalBreakdown(userRows),
    };
  }

  const pRows = filterByPortfolio(userRows, portfolioName);
  const meta = portfolioMetadata(pRows);
  let holdings: Holding[] = [];

  if (meta.portfolio_type === PORTFOLIO_TYPE_GROWTH) {
    holdings = stocksToHoldings(growthStocksFromRows(pRows, meta.investor_birth_date));
  } else if (meta.portfolio_type === "Stocks") {
    holdings = await buildStocksHoldings(
      pRows,
      purchases,
      dividends,
      username,
      portfolioName
    );
  } else {
    let stocks: StockRow[] = stocksFromRows(pRows);
    if (meta.portfolio_type === "Kids" && meta.portfolio_birth_date) {
      stocks = kidsApplyTargets(stocks, meta.portfolio_birth_date);
    }
    holdings = stocksToHoldings(stocks);
  }

  const totalValue = portfolioTotal(
    holdings.map((h) => ({ current_value: h.current_value })),
    meta.portfolio_type
  );
  const weightedTer =
    totalValue > 0
      ? holdings.reduce(
          (s, h) => s + (h.current_value / totalValue) * h.expense_ratio,
          0
        )
      : 0;
  const targetSum = holdings.reduce((s, h) => s + h.target_allocation, 0);
  const active = holdings.filter((h) => h.ticker !== "__PLACEHOLDER__");

  const result: PortfolioDetail = {
    name: portfolioName,
    portfolio_type: meta.portfolio_type,
    total_value: totalValue,
    target_sum: Math.round(targetSum * 100) / 100,
    weighted_ter: Math.round(weightedTer * 100) / 100,
    monthly_invest: meta.monthly_invest,
    uninvested_cash: meta.uninvested_cash,
    safe_liquidity: meta.safe_liquidity,
    holdings,
    holdings_count: active.length,
  };

  if (meta.portfolio_type === "Stocks") {
    const totalInvested = active.reduce(
      (s, h) => s + ((h as Holding & { total_invested?: number }).total_invested ?? 0),
      0
    );
    const profit = totalValue - totalInvested;
    const sectors = new Set(
      active.map((h) => (h as Holding & { sector?: string }).sector).filter(Boolean)
    );
    result.total_invested = Math.round(totalInvested * 100) / 100;
    result.profit = Math.round(profit * 100) / 100;
    result.profit_pct =
      totalInvested > 0 ? Math.round((profit / totalInvested) * 10000) / 100 : 0;
    result.volumes_count = active.reduce(
      (s, h) => s + ((h as Holding & { quantity?: number }).quantity ?? 0),
      0
    );
    result.num_sectors = sectors.size;
  } else if (meta.portfolio_type === PORTFOLIO_TYPE_GROWTH || meta.portfolio_type === "Kids") {
    result.total_invested = totalInvestedFromLog(
      logRows,
      username,
      portfolioName,
      meta.uninvested_cash
    );
  }

  return result;
}

function totalInvestedFromLog(
  log: MasterRow[],
  username: string,
  portfolioName: string,
  uninvested: number
): number {
  const subset = log.filter(
    (r) =>
      String(r.username) === username &&
      String(r.portfolio_name) === portfolioName
  );
  const sum = subset.reduce((s, r) => s + Number(r.Investment ?? r.investment ?? 0), 0);
  return Math.round(Math.max(0, sum - Math.max(0, uninvested)) * 100) / 100;
}
