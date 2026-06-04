import { AllocationResult, ChartData } from "../api";
import { AllocationTable } from "./AllocationTable";
import { DonutPieChart } from "./DonutPieChart";
import { KpiCard } from "./KpiCard";
import { TimeSeriesChart } from "./TimeSeriesChart";
import { Card } from "./ui/Card";
import { PrimaryButton, SecondaryButton } from "./ui/Buttons";
import { SectionHeader } from "./ui/SectionHeader";
import { StyleSheet, View } from "react-native";
import { spacing } from "../theme";

function formatEuro(value: number) {
  return `€${value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

type Props = {
  portfolioType: string;
  allocation: AllocationResult | null;
  charts: ChartData | null;
  busy: boolean;
  onCalculate: () => void;
  onLog?: () => void;
};

export function GrowthAllocationPanel({
  portfolioType,
  allocation,
  charts,
  busy,
  onCalculate,
  onLog,
}: Props) {
  const isGrowth = portfolioType === "Growth";
  return (
    <View>
      <Card>
        <SectionHeader title="🎯 Action Center" />
        <SecondaryButton
          label="🧮 Calculate allocation"
          onPress={onCalculate}
          disabled={busy}
          loading={busy}
        />
      </Card>

      {allocation ? (
        <>
          <View style={styles.kpiRow}>
            {isGrowth ? (
              <>
                <KpiCard
                  label="ETF investment"
                  value={formatEuro(allocation.total_etf_investment)}
                  accent
                />
                <KpiCard
                  label="Safe liquidity"
                  value={formatEuro(allocation.safe_liquidity_after)}
                />
              </>
            ) : (
              <>
                <KpiCard
                  label="Monthly contribution"
                  value={formatEuro(allocation.monthly_contribution)}
                  accent
                />
                <KpiCard
                  label="Total investment"
                  value={formatEuro(allocation.total_etf_investment)}
                />
              </>
            )}
          </View>
          <AllocationTable rows={allocation.recommendations} />
          {charts ? (
            <>
              <SectionHeader title="📉 Allocation visuals" />
              <DonutPieChart
                title="After Investment"
                data={allocation.recommendations
                  .filter((r) => r.stock !== "EGLN.UK" && r.new_value > 0)
                  .map((r) => ({ name: r.stock, value: r.new_value }))}
              />
              <TimeSeriesChart data={charts.time_series} />
            </>
          ) : null}
          {onLog ? (
            <PrimaryButton label="💾 Log to history" onPress={onLog} disabled={busy} />
          ) : null}
        </>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  kpiRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md, marginBottom: spacing.md },
});
