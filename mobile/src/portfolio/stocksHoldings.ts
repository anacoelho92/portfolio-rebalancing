import type { Holding } from "../types";
import { safeFloat, type MasterRow } from "./core";
import { filterForUser } from "./core";
import { stocksFromRows } from "./data";

function purchaseDps(p: Record<string, unknown>): number {
  const price = safeFloat(p.unit_price);
  const dy = safeFloat(p.dividend_yield);
  if (price <= 0) return 0;
  return (dy / 100) * price;
}

function purchasesForPortfolio(
  sheet: MasterRow[],
  username: string,
  portfolioName: string
) {
  return sheet.filter(
    (r) =>
      String(r.username) === username &&
      String(r.portfolio_name) === portfolioName
  );
}

function dividendMap(
  dividends: MasterRow[],
  username: string,
  portfolioName: string
): Record<string, number> {
  const out: Record<string, number> = {};
  for (const r of dividends) {
    if (
      String(r.username) !== username ||
      String(r.portfolio_name) !== portfolioName
    )
      continue;
    const t = String(r.ticker ?? "").toUpperCase();
    out[t] = (out[t] ?? 0) + safeFloat(r.amount);
  }
  return out;
}

export function aggregate(
  purchases: MasterRow[],
  divMap: Record<string, number>,
  marketOverrides: Record<string, number>
) {
  const buckets: Record<
    string,
    {
      ticker: string;
      name: string;
      sector: string;
      industry: string;
      quantity: number;
      invested: number;
      dpsQty: number;
      lowest: number | null;
    }
  > = {};

  for (const p of purchases) {
    const ticker = String(p.ticker ?? p.stock_name ?? "")
      .trim()
      .toUpperCase();
    if (!ticker) continue;
    const qty = safeFloat(p.quantity);
    const unitPrice = safeFloat(p.unit_price);
    const invested = unitPrice * qty;
    const dps = purchaseDps(p);
    if (!buckets[ticker]) {
      buckets[ticker] = {
        ticker,
        name: String(p.stock_name ?? p.name ?? ticker),
        sector: String(p.sector ?? ""),
        industry: String(p.industry ?? ""),
        quantity: 0,
        invested: 0,
        dpsQty: 0,
        lowest: unitPrice > 0 ? unitPrice : null,
      };
    }
    const b = buckets[ticker]!;
    b.quantity += qty;
    b.invested += invested;
    b.dpsQty += dps * qty;
    if (unitPrice > 0 && (b.lowest == null || unitPrice < b.lowest)) b.lowest = unitPrice;
  }

  return Object.values(buckets)
    .sort((a, b) => a.ticker.localeCompare(b.ticker))
    .map((b) => {
      const qty = b.quantity;
      const invested = b.invested;
      const avg = qty > 0 ? invested / qty : 0;
      const market = marketOverrides[b.ticker] ?? invested;
      const pps = qty > 0 ? market / qty : 0;
      const divYield = pps > 0 ? (b.dpsQty / qty / pps) * 100 : 0;
      return {
        ticker: b.ticker,
        name: b.name,
        quantity: Math.round(qty * 10000) / 10000,
        invested_value: Math.round(invested * 100) / 100,
        avg_price: Math.round(avg * 10000) / 10000,
        market_value: Math.round(market * 100) / 100,
        div_yield: Math.round(divYield * 100) / 100,
        sector: b.sector,
        industry: b.industry,
        received_yoc:
          invested > 0
            ? Math.round(((divMap[b.ticker] ?? 0) / invested) * 10000) / 100
            : 0,
      };
    });
}

export async function buildStocksHoldings(
  pRows: MasterRow[],
  purchasesSheet: MasterRow[],
  dividendsSheet: MasterRow[],
  username: string,
  portfolioName: string
): Promise<(Holding & { total_invested?: number; quantity?: number; sector?: string; dividend_yield?: number })[]> {
  const base = stocksFromRows(pRows);
  const overrides: Record<string, number> = {};
  for (const s of base) {
    overrides[s.name.toUpperCase()] = s.current_value;
  }

  let purchases = purchasesForPortfolio(purchasesSheet, username, portfolioName);
  if (!purchases.length && base.length) {
    purchases = base.map((s) => ({
      username,
      portfolio_name: portfolioName,
      ticker: s.name.toUpperCase(),
      stock_name: s.name,
      unit_price: s.average_price,
      quantity: s.quantity,
      sector: s.sector,
      industry: s.industry,
    }));
  }

  const divM = dividendMap(dividendsSheet, username, portfolioName);
  const summaries = aggregate(purchases, divM, overrides);
  const existing = Object.fromEntries(base.map((s) => [s.name.toUpperCase(), s]));

  return summaries.map((summary) => {
    const prev = existing[summary.ticker] ?? existing[summary.name] ?? {};
    return {
      ticker: summary.ticker,
      current_value: summary.market_value,
      target_allocation: safeFloat(prev.target_allocation),
      tolerance: safeFloat(prev.tolerance, 2),
      expense_ratio: safeFloat(prev.expense_ratio),
      total_invested: summary.invested_value,
      quantity: summary.quantity,
      sector: summary.sector,
      dividend_yield: summary.div_yield,
    };
  });
}
