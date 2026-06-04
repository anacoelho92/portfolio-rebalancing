/** Kids / proportional allocation (port of _allocate_standard_portfolio). */

export type LiveStock = {
  name: string;
  current_value: number;
  target_allocation: number;
  tolerance?: number;
};

export function allocateStandardPortfolio(
  liveStocks: LiveStock[],
  monthlyContribution: number
): { investments: Record<string, number>; leftover: number } {
  const totalCurrent = liveStocks.reduce((s, x) => s + x.current_value, 0);
  const coreTarget = liveStocks.reduce((s, x) => s + x.target_allocation, 0);
  if (Math.abs(coreTarget - 100) > 0.01) {
    throw new Error(
      `Target allocations sum to ${coreTarget.toFixed(1)}% — they must sum to 100%.`
    );
  }

  let remaining = monthlyContribution;
  const finalInvestments: Record<string, number> = Object.fromEntries(
    liveStocks.map((s) => [s.name, 0])
  );
  const totalTheoretical = totalCurrent + remaining;

  if (remaining > 0 && liveStocks.length) {
    type Item = {
      name: string;
      Gap: number;
      stock: LiveStock;
      deviation: number;
      below_min_band: boolean;
      below_target: boolean;
      invest: number;
      needed_band: number;
    };
    const stockData: Item[] = [];
    let sumPosDev = 0;

    for (const stock of liveStocks) {
      const cw =
        totalCurrent > 0 ? (stock.current_value / totalCurrent) * 100 : 0;
      const tw = stock.target_allocation;
      const deviation = tw - cw;
      const minBand = tw - (stock.tolerance ?? 0);
      const belowMin = cw < minBand;
      const belowTarget = deviation > 0;
      if (belowTarget) sumPosDev += deviation;
      const gap = (totalTheoretical * tw) / 100 - stock.current_value;
      stockData.push({
        name: stock.name,
        Gap: gap,
        stock,
        deviation,
        below_min_band: belowMin,
        below_target: belowTarget,
        invest: 0,
        needed_band: 0,
      });
    }

    let totalNeededBand = 0;
    for (const item of stockData) {
      if (item.below_min_band) {
        const minEur =
          (totalTheoretical *
            (item.stock.target_allocation - (item.stock.tolerance ?? 0))) /
          100;
        item.needed_band = Math.max(0, minEur - item.stock.current_value);
        totalNeededBand += item.needed_band;
      }
    }

    if (totalNeededBand > 0 && remaining > 0) {
      if (totalNeededBand <= remaining) {
        for (const item of stockData) {
          if (item.needed_band > 0) {
            item.invest += item.needed_band;
            remaining -= item.needed_band;
          }
        }
      } else {
        for (const item of stockData) {
          if (item.needed_band > 0) {
            item.invest += (item.needed_band / totalNeededBand) * remaining;
          }
        }
        remaining = 0;
      }
    }

    if (remaining > 0 && sumPosDev > 0) {
      const funds = remaining;
      for (const item of stockData) {
        if (item.below_target) {
          const prop = (item.deviation / sumPosDev) * funds;
          const maxInv = Math.max(0, item.Gap - item.invest);
          item.invest += Math.min(prop, maxInv);
          remaining -= Math.min(prop, maxInv);
        }
      }
    }

    if (remaining >= 0.01) {
      const sorted = [...stockData].sort(
        (a, b) => b.Gap - b.invest - (a.Gap - a.invest)
      );
      for (const g of sorted) {
        if (remaining < 0.01) break;
        const needed = Math.max(0, g.Gap - g.invest);
        if (needed > 0) {
          const alloc = Math.min(remaining, needed);
          g.invest += alloc;
          remaining -= alloc;
        }
      }
    }

    for (const item of stockData) {
      finalInvestments[item.name] = item.invest;
    }
  }

  let totalRounded = 0;
  for (const ticker of Object.keys(finalInvestments)) {
    const rounded = Math.floor(finalInvestments[ticker]!);
    finalInvestments[ticker] = rounded;
    totalRounded += rounded;
  }

  let leftover = monthlyContribution - totalRounded;
  if (leftover >= 1 && liveStocks.length) {
    const sorted = [...liveStocks].sort(
      (a, b) => b.target_allocation - a.target_allocation
    );
    if (sorted[0]) {
      finalInvestments[sorted[0].name] =
        (finalInvestments[sorted[0].name] ?? 0) + Math.floor(leftover);
    }
    leftover = monthlyContribution - Object.values(finalInvestments).reduce((a, b) => a + b, 0);
  }

  return { investments: finalInvestments, leftover };
}
