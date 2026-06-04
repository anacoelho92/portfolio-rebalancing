import type { AddStockPurchaseInput, StockPurchasesPayload } from "../types";
import { readWorksheetRows, writeWorksheetRows } from "../firestore/worksheets";
import { safeFloat, type MasterRow } from "./core";
import { aggregate } from "./stocksHoldings";

function randomId() {
  return `p-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function purchasesFromRows(rows: MasterRow[]) {
  return rows.map((row) => ({
    id: String(row.purchase_id ?? randomId()),
    ticker: String(row.ticker ?? "").toUpperCase(),
    name: String(row.stock_name ?? row.ticker ?? ""),
    sector: String(row.sector ?? ""),
    industry: String(row.industry ?? ""),
    country: String(row.country ?? ""),
    currency: String(row.currency ?? ""),
    unit_price: safeFloat(row.unit_price),
    quantity: safeFloat(row.quantity),
    dividend_yield: safeFloat(row.dividend_yield),
    dps: safeFloat(row.dps),
  }));
}

function expandUnits(purchases: ReturnType<typeof purchasesFromRows>) {
  const units: StockPurchasesPayload["units"] = [];
  for (const p of purchases) {
    const qty = p.quantity;
    if (qty <= 0) continue;
    const whole = Math.round(qty);
    if (Math.abs(qty - whole) < 1e-6 && whole >= 1) {
      for (let i = 0; i < whole; i++) {
        units.push({
          unit_key: `${p.id}#${i}`,
          purchase_id: p.id,
          unit_index: i,
          ticker: p.ticker,
          price: p.unit_price,
          currency: p.currency,
          dividend_yield: p.dividend_yield,
          fractional: false,
        });
      }
    } else {
      units.push({
        unit_key: `${p.id}#frac`,
        purchase_id: p.id,
        unit_index: 0,
        ticker: p.ticker,
        price: p.unit_price,
        currency: p.currency,
        dividend_yield: p.dividend_yield,
        fractional: true,
        display_qty: qty,
      });
    }
  }
  return units;
}

async function buildPayload(
  master: MasterRow[],
  username: string,
  portfolioName: string,
  purchases: ReturnType<typeof purchasesFromRows>
): Promise<StockPurchasesPayload> {
  const pRows = master.filter(
    (r) =>
      String(r.username) === username && String(r.portfolio_name) === portfolioName
  );
  const overrides: Record<string, number> = {};
  for (const r of pRows) {
    if (String(r.stock_name) !== "__PLACEHOLDER__") {
      overrides[String(r.stock_name).toUpperCase()] = safeFloat(r.current_value);
    }
  }
  const divRows = await readWorksheetRows("Dividends");
  const divMap: Record<string, number> = {};
  for (const r of divRows) {
    if (
      String(r.username) === username &&
      String(r.portfolio_name) === portfolioName
    ) {
      const t = String(r.ticker).toUpperCase();
      divMap[t] = (divMap[t] ?? 0) + safeFloat(r.amount);
    }
  }
  const summaries = aggregate(
    purchases.map((p) => ({
      username,
      portfolio_name: portfolioName,
      ticker: p.ticker,
      stock_name: p.name,
      unit_price: p.unit_price,
      quantity: p.quantity,
      sector: p.sector,
      industry: p.industry,
      dividend_yield: p.dividend_yield,
    })),
    divMap,
    overrides
  );
  const targets: Record<string, number> = {};
  const tolerances: Record<string, number> = {};
  for (const r of pRows) {
    const t = String(r.stock_name).toUpperCase();
    targets[t] = safeFloat(r.target_allocation);
    tolerances[t] = safeFloat(r.tolerance, 2);
  }
  const totalMv = summaries.reduce((s, x) => s + x.market_value, 0);
  for (const s of summaries) {
    (s as { current_pct?: number }).current_pct =
      totalMv > 0 ? Math.round((s.market_value / totalMv) * 10000) / 100 : 0;
    (s as { target_allocation?: number }).target_allocation =
      Math.round((targets[s.ticker] ?? 0) * 100) / 100;
    (s as { tolerance?: number }).tolerance = Math.round((tolerances[s.ticker] ?? 2) * 100) / 100;
  }
  const units = expandUnits(purchases);
  const byTicker: Record<string, typeof units> = {};
  for (const u of units) {
    if (!byTicker[u.ticker]) byTicker[u.ticker] = [];
    byTicker[u.ticker]!.push(u);
  }
  return {
    purchases,
    units,
    units_by_ticker: byTicker,
    summaries: summaries as StockPurchasesPayload["summaries"],
    total_market_value: Math.round(totalMv * 100) / 100,
    total_invested: Math.round(summaries.reduce((s, x) => s + x.invested_value, 0) * 100) / 100,
  };
}

async function writePurchases(
  username: string,
  portfolioName: string,
  purchases: ReturnType<typeof purchasesFromRows>
) {
  const sheet = await readWorksheetRows("StockPurchases");
  const rest = sheet.filter(
    (r) =>
      !(String(r.username) === username && String(r.portfolio_name) === portfolioName)
  );
  const rows = purchases.map((p) => ({
    username,
    portfolio_name: portfolioName,
    purchase_id: p.id,
    ticker: p.ticker,
    stock_name: p.name,
    sector: p.sector,
    industry: p.industry,
    country: p.country,
    currency: p.currency,
    unit_price: p.unit_price,
    quantity: p.quantity,
    dividend_yield: p.dividend_yield,
    dps: (p.dividend_yield / 100) * p.unit_price,
  }));
  await writeWorksheetRows("StockPurchases", [...rest, ...rows]);
}

export async function fetchStockPurchasesPayload(
  master: MasterRow[],
  username: string,
  portfolioName: string
): Promise<StockPurchasesPayload> {
  const sheet = await readWorksheetRows("StockPurchases");
  const mine = sheet.filter(
    (r) =>
      String(r.username) === username && String(r.portfolio_name) === portfolioName
  );
  return buildPayload(master, username, portfolioName, purchasesFromRows(mine));
}

export async function addStockPurchase(
  master: MasterRow[],
  username: string,
  portfolioName: string,
  body: AddStockPurchaseInput
) {
  const sheet = await readWorksheetRows("StockPurchases");
  const mine = sheet.filter(
    (r) =>
      String(r.username) === username && String(r.portfolio_name) === portfolioName
  );
  const purchases = purchasesFromRows(mine);
  purchases.push({
    id: randomId(),
    ticker: body.ticker.toUpperCase(),
    name: body.ticker.toUpperCase(),
    sector: body.sector ?? "",
    industry: body.industry ?? "",
    country: body.country ?? "",
    currency: body.currency ?? "",
    unit_price: body.unit_price,
    quantity: body.quantity,
    dividend_yield: body.dividend_yield ?? 0,
    dps: ((body.dividend_yield ?? 0) / 100) * body.unit_price,
  });
  await writePurchases(username, portfolioName, purchases);
  return buildPayload(master, username, portfolioName, purchases);
}

export async function deleteStockUnit(
  master: MasterRow[],
  username: string,
  portfolioName: string,
  unitKey: string
) {
  const sheet = await readWorksheetRows("StockPurchases");
  const mine = sheet.filter(
    (r) =>
      String(r.username) === username && String(r.portfolio_name) === portfolioName
  );
  let purchases = purchasesFromRows(mine);
  const [pid, idxStr] = unitKey.split("#");
  const idx = idxStr === "frac" ? -1 : parseInt(idxStr, 10);
  purchases = purchases
    .map((p) => {
      if (p.id !== pid) return p;
      if (idxStr === "frac") return { ...p, quantity: 0 };
      const newQty = Math.max(0, Math.floor(p.quantity) - 1);
      return { ...p, quantity: newQty };
    })
    .filter((p) => p.quantity > 0);
  await writePurchases(username, portfolioName, purchases);
  return buildPayload(master, username, portfolioName, purchases);
}

export async function updateStockMarketValues(
  master: MasterRow[],
  username: string,
  portfolioName: string,
  marketValues: Record<string, number>
) {
  let rows = [...master];
  for (const [ticker, value] of Object.entries(marketValues)) {
    rows = rows.map((r) =>
      String(r.username) === username &&
      String(r.portfolio_name) === portfolioName &&
      String(r.stock_name).toUpperCase() === ticker.toUpperCase()
        ? { ...r, current_value: value }
        : r
    );
  }
  const { saveMaster } = await import("./actions");
  await saveMaster(rows);
  return fetchStockPurchasesPayload(rows, username, portfolioName);
}

// Export aggregate for stocksHoldings - fix stocksHoldings to not export aggregate from wrong place
