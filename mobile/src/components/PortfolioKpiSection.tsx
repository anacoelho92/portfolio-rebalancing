import type { ReactNode } from "react";
import { StyleSheet, View } from "react-native";
import type { PortfolioDetail } from "../api";
import { KpiCard } from "./KpiCard";
import { spacing } from "../theme";

type Props = {
  detail: PortfolioDetail;
};

function formatEuro(value: number) {
  return `€${value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function formatCount(n: number) {
  return n.toLocaleString("en-US", { maximumFractionDigits: 0 });
}

function KpiRow({ children }: { children: ReactNode }) {
  return <View style={styles.row}>{children}</View>;
}

export function PortfolioKpiSection({ detail }: Props) {
  const pType = detail.portfolio_type;
  const isStocks = pType === "Stocks";
  const isKids = pType === "Kids";
  const isGrowthOrKids = pType === "Growth" || isKids;

  if (isStocks) {
    const profit = detail.profit ?? 0;
    const profitPct = detail.profit_pct ?? 0;
    const profitPositive = profit >= 0;
    const prefix = profitPositive ? "+" : "";

    const profitEuro = `${prefix}${formatEuro(Math.abs(profit))}`;
    const profitPctStr = `${prefix}${profitPct.toFixed(2)}%`;

    return (
      <View style={styles.wrap}>
        <KpiRow>
          <KpiCard
            label="Total Market Value"
            value={formatEuro(detail.total_value)}
            accent
            compact
          />
          <KpiCard
            label="Total Invested"
            value={formatEuro(detail.total_invested ?? 0)}
            compact
          />
        </KpiRow>
        <KpiRow>
          <KpiCard
            label="Profit"
            value={profitEuro}
            subValue={profitPctStr}
            tone={profitPositive ? "positive" : "negative"}
            compact
          />
          <KpiCard
            label="Volumes Count"
            value={formatCount(detail.volumes_count ?? 0)}
            compact
          />
        </KpiRow>
        <KpiRow>
          <KpiCard
            label="Stocks by Sectors"
            value={`${detail.holdings_count ?? 0} / ${detail.num_sectors ?? 0}`}
            compact
          />
          <KpiCard
            label="Dividend Yield"
            value={`${(detail.portfolio_div_yield ?? 0).toFixed(2)}%`}
            compact
          />
          <KpiCard
            label="Yield on Cost"
            value={`${(detail.portfolio_yoc ?? 0).toFixed(2)}%`}
            compact
          />
        </KpiRow>
      </View>
    );
  }

  return (
    <KpiRow>
      <KpiCard
        label="Total Value"
        value={formatEuro(detail.total_value)}
        accent
        compact
      />
      <KpiCard
        label="Weighted TER"
        value={`${(detail.weighted_ter ?? 0).toFixed(2)}%`}
        compact
      />
      {isGrowthOrKids ? (
        <KpiCard
          label="Total Invested"
          value={formatEuro(detail.total_invested ?? 0)}
          compact
        />
      ) : (
        <KpiCard
          label="Monthly Budget"
          value={formatEuro(detail.monthly_invest ?? 0)}
          compact
        />
      )}
    </KpiRow>
  );
}

const styles = StyleSheet.create({
  wrap: { width: "100%", marginBottom: spacing.md, gap: spacing.sm },
  row: {
    flexDirection: "row",
    width: "100%",
    gap: spacing.sm,
    marginBottom: spacing.sm,
    alignItems: "stretch",
  },
});
