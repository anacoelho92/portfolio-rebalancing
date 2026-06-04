import type { ReactNode } from "react";
import { StyleSheet, Text, TextInput, View } from "react-native";
import type { Holding } from "../api";
import { colors, spacing } from "../theme";
import { AllocationProgressBar } from "./AllocationProgressBar";
import { Card } from "./ui/Card";

const GROWTH_TICKER_ORDER = ["SPYL.DE", "IXUA.DE", "VFEA.DE", "EGLN.UK"];

type Props = {
  holdings: Holding[];
  portfolioType: string;
  busy?: boolean;
  monthlyInvest?: string;
  safeLiquidity?: string;
  onMonthlyInvestChange?: (v: string) => void;
  onSafeLiquidityChange?: (v: string) => void;
  onUpdate: (ticker: string, field: keyof Holding, value: string) => void;
};

function sortHoldings(rows: Holding[], isGrowth: boolean): Holding[] {
  if (!isGrowth) return rows;
  return [...rows].sort((a, b) => {
    const ia = GROWTH_TICKER_ORDER.indexOf(a.ticker);
    const ib = GROWTH_TICKER_ORDER.indexOf(b.ticker);
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });
}

function FieldRow({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <View style={styles.fieldRow}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <View style={styles.fieldValue}>{children}</View>
    </View>
  );
}

export function PortfolioManagementTable({
  holdings,
  portfolioType,
  busy,
  monthlyInvest,
  safeLiquidity,
  onMonthlyInvestChange,
  onSafeLiquidityChange,
  onUpdate,
}: Props) {
  const isGrowth = portfolioType === "Growth";
  const isKids = portfolioType === "Kids";
  const rows = sortHoldings(holdings, isGrowth);
  const totalValue = rows.reduce((s, r) => s + (r.current_value || 0), 0);

  if (!rows.length) {
    return (
      <Text style={styles.empty}>No holdings in this portfolio yet.</Text>
    );
  }

  return (
    <View>
      {isGrowth && onMonthlyInvestChange && onSafeLiquidityChange ? (
        <View style={styles.settingsRow}>
          <View style={styles.settingCell}>
            <Text style={styles.settingLabel}>Monthly invest (€)</Text>
            <TextInput
              style={styles.settingInput}
              keyboardType="decimal-pad"
              value={monthlyInvest ?? ""}
              onChangeText={onMonthlyInvestChange}
              editable={!busy}
            />
          </View>
          <View style={styles.settingCell}>
            <Text style={styles.settingLabel}>Safe liquidity (€)</Text>
            <TextInput
              style={styles.settingInput}
              keyboardType="decimal-pad"
              value={safeLiquidity ?? ""}
              onChangeText={onSafeLiquidityChange}
              editable={!busy}
            />
          </View>
        </View>
      ) : null}

      {rows.map((row, index) => {
        const currentPct =
          totalValue > 0 ? (row.current_value / totalValue) * 100 : 0;
        const targetPct = row.target_allocation ?? 0;

        return (
          <Card key={row.ticker} style={styles.holdingCard}>
            <View style={styles.cardInner}>
              <Text style={styles.cardIndex}>{index + 1}</Text>
              <View style={styles.cardBody}>
                <Text style={styles.ticker} numberOfLines={1}>
                  {row.ticker}
                </Text>

                <FieldRow label="Value (€)">
                  <TextInput
                    style={styles.valueInput}
                    keyboardType="decimal-pad"
                    value={String(row.current_value)}
                    onChangeText={(v) =>
                      onUpdate(row.ticker, "current_value", v)
                    }
                    editable={!busy}
                  />
                </FieldRow>

                <AllocationProgressBar
                  currentPct={currentPct}
                  targetPct={targetPct}
                  tolerancePct={row.tolerance ?? 2}
                  terPct={row.expense_ratio ?? 0}
                />
              </View>
            </View>
          </Card>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  empty: { color: colors.textMuted, fontSize: 13 },
  settingsRow: {
    flexDirection: "row",
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  settingCell: { flex: 1 },
  settingLabel: {
    color: colors.text,
    fontSize: 12,
    fontWeight: "600",
    marginBottom: 4,
  },
  settingInput: {
    backgroundColor: colors.bg,
    borderRadius: 8,
    padding: spacing.sm,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
    fontSize: 13,
  },
  holdingCard: {
    marginBottom: spacing.sm,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.sm,
    backgroundColor: colors.bg,
  },
  cardInner: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 6,
  },
  cardIndex: {
    color: colors.textMuted,
    fontSize: 14,
    fontWeight: "700",
    width: 20,
    lineHeight: 18,
    textAlign: "right",
  },
  cardBody: {
    flex: 1,
    minWidth: 0,
  },
  ticker: {
    color: colors.text,
    fontSize: 15,
    fontWeight: "700",
    lineHeight: 18,
  },
  fieldRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 4,
  },
  fieldLabel: {
    color: colors.textMuted,
    fontSize: 12,
    flex: 1,
  },
  fieldValue: {
    flex: 1,
    alignItems: "flex-end",
  },
  valueInput: {
    backgroundColor: colors.bg,
    borderRadius: 6,
    paddingVertical: 4,
    paddingHorizontal: 6,
    color: colors.text,
    fontSize: 13,
    borderWidth: 1,
    borderColor: colors.accent,
    minWidth: 96,
    textAlign: "right",
  },
});
