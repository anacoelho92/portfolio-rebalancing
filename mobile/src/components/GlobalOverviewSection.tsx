import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import type { PortfolioDetail } from "../api";
import { colors, spacing } from "../theme";
import { DonutPieChart } from "./DonutPieChart";
import { KpiCard } from "./KpiCard";
import { Card } from "./ui/Card";
import { InfoBanner } from "./ui/InfoBanner";
import { SectionHeader } from "./ui/SectionHeader";

type Props = {
  detail: PortfolioDetail | null;
  loading?: boolean;
};

function formatEuro(value: number) {
  return `€${value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function GlobalOverviewSection({ detail, loading }: Props) {
  if (loading && !detail) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator color={colors.accent} />
      </View>
    );
  }

  const pieData = (detail?.breakdown ?? [])
    .filter((b) => b.total_value > 0)
    .map((b) => ({ name: b.name, value: b.total_value }));

  return (
    <View style={styles.wrap}>
      <SectionHeader title="🌍 Global Portfolio Overview" />
      <View style={styles.kpiRow}>
        <KpiCard
          label="Total value"
          value={formatEuro(detail?.total_value ?? 0)}
          accent
        />
      </View>
      <Card>
        {pieData.length > 0 ? (
          <DonutPieChart title="By portfolio" data={pieData} />
        ) : (
          <InfoBanner message="No value invested yet or no data available." />
        )}
      </Card>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginBottom: spacing.md },
  loading: { paddingVertical: spacing.xl, alignItems: "center" },
  kpiRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.md,
    marginBottom: spacing.md,
  },
});
