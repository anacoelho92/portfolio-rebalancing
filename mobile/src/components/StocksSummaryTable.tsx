import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import type { StockSummary } from "../api";
import { colors, spacing } from "../theme";
import { AllocationProgressBar } from "./AllocationProgressBar";
import { Card } from "./ui/Card";

type Props = {
  rows: StockSummary[];
  totalMarketValue: number;
  busy?: boolean;
  onSave: (marketValues: Record<string, number>) => Promise<void>;
};

function formatNum(n: number, decimals = 2) {
  return n.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function formatEuro(n: number) {
  return `€${formatNum(n)}`;
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.stat}>
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={styles.statValue}>{value}</Text>
    </View>
  );
}

export function StocksSummaryTable({
  rows,
  totalMarketValue,
  busy,
  onSave,
}: Props) {
  const [marketEdits, setMarketEdits] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const next: Record<string, string> = {};
    for (const r of rows) {
      next[r.ticker] = String(r.market_value);
    }
    setMarketEdits(next);
  }, [rows]);

  const liveTotal = useMemo(() => {
    return rows.reduce((sum, r) => {
      const v = parseFloat(marketEdits[r.ticker] ?? "");
      return sum + (Number.isFinite(v) ? v : r.market_value);
    }, 0);
  }, [rows, marketEdits]);

  const dirty = useMemo(() => {
    return rows.some((r) => {
      const edited = parseFloat(marketEdits[r.ticker] ?? "");
      return (
        Number.isFinite(edited) &&
        Math.abs(edited - r.market_value) > 0.005
      );
    });
  }, [rows, marketEdits]);

  function marketValueFor(row: StockSummary) {
    const v = parseFloat(marketEdits[row.ticker] ?? "");
    return Number.isFinite(v) ? v : row.market_value;
  }

  function currentPctFor(row: StockSummary) {
    const mv = marketValueFor(row);
    const total = liveTotal > 0 ? liveTotal : totalMarketValue;
    return total > 0 ? (mv / total) * 100 : row.current_pct ?? 0;
  }

  async function handleSave() {
    setError(null);
    const payload: Record<string, number> = {};
    for (const r of rows) {
      const v = parseFloat(marketEdits[r.ticker] ?? "");
      if (!Number.isFinite(v) || v < 0) {
        setError(`Invalid market value for ${r.ticker}`);
        return;
      }
      payload[r.ticker] = v;
    }
    setSaving(true);
    try {
      await onSave(payload);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  if (!rows.length) {
    return (
      <View style={styles.wrap}>
        <Text style={styles.title}>Portfolio details</Text>
        <Text style={styles.empty}>No purchases yet. Add a purchase to see holdings.</Text>
      </View>
    );
  }

  return (
    <View style={styles.wrap}>
      <Text style={styles.title}>Portfolio details</Text>
      {error ? <Text style={styles.error}>{error}</Text> : null}

      {rows.map((row, index) => {
        const currentPct = currentPctFor(row);
        const targetPct = row.target_allocation ?? 0;

        return (
          <Card key={row.ticker} style={styles.stockCard}>
            <View style={styles.cardInner}>
              <Text style={styles.cardIndex}>{index + 1}</Text>
              <View style={styles.cardBody}>
                <Text style={styles.ticker} numberOfLines={1}>
                  {row.ticker}
                </Text>
                {row.name && row.name !== row.ticker ? (
                  <Text style={styles.name} numberOfLines={1}>
                    {row.name}
                  </Text>
                ) : null}

                <View style={styles.marketRow}>
                  <Text style={styles.marketLabel}>Market (€)</Text>
                  <TextInput
                    style={styles.marketInput}
                    keyboardType="decimal-pad"
                    value={marketEdits[row.ticker] ?? ""}
                    onChangeText={(text) =>
                      setMarketEdits((prev) => ({ ...prev, [row.ticker]: text }))
                    }
                    editable={!busy && !saving}
                  />
                </View>

                <AllocationProgressBar
                  currentPct={currentPct}
                  targetPct={targetPct}
                  tolerancePct={row.tolerance ?? 2}
                />

                <View style={styles.statsGrid}>
                  <Stat label="Invested" value={formatEuro(row.invested_value)} />
                  <Stat label="Qty" value={String(Math.round(row.quantity))} />
                  <Stat label="Avg price" value={formatNum(row.avg_price, 4)} />
                  <Stat label="Div %" value={`${formatNum(row.div_yield)}%`} />
                  <Stat label="YoC" value={`${formatNum(row.yoc ?? 0)}%`} />
                  <Stat
                    label="Recv YoC"
                    value={`${formatNum(row.received_yoc ?? 0)}%`}
                  />
                </View>
              </View>
            </View>
          </Card>
        );
      })}

      {dirty ? (
        <Pressable
          style={[styles.saveBtn, (busy || saving) && styles.btnDisabled]}
          onPress={handleSave}
          disabled={busy || saving}
        >
          {saving ? (
            <ActivityIndicator color="#fff" size="small" />
          ) : (
            <Text style={styles.saveBtnText}>Save market values</Text>
          )}
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    marginBottom: spacing.md,
  },
  title: {
    color: colors.text,
    fontWeight: "700",
    fontSize: 16,
    marginBottom: spacing.md,
  },
  empty: { color: colors.textMuted, fontSize: 13 },
  error: { color: colors.danger, marginBottom: spacing.sm, fontSize: 13 },
  stockCard: {
    marginBottom: spacing.sm,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.sm,
    backgroundColor: colors.card,
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
  name: {
    color: colors.textMuted,
    fontSize: 11,
    lineHeight: 14,
    marginTop: 1,
  },
  marketRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 4,
  },
  marketLabel: {
    color: colors.textMuted,
    fontSize: 12,
  },
  marketInput: {
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
  statsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 4,
    marginTop: 4,
  },
  stat: {
    width: "47%",
    backgroundColor: colors.bg,
    borderRadius: 6,
    paddingVertical: 4,
    paddingHorizontal: 6,
  },
  statLabel: {
    color: colors.textMuted,
    fontSize: 10,
    marginBottom: 2,
  },
  statValue: {
    color: colors.text,
    fontSize: 12,
    fontWeight: "600",
  },
  saveBtn: {
    backgroundColor: colors.accent,
    borderRadius: 10,
    padding: spacing.md,
    alignItems: "center",
    marginTop: spacing.md,
  },
  saveBtnText: { color: "#fff", fontWeight: "700" },
  btnDisabled: { opacity: 0.6 },
});
