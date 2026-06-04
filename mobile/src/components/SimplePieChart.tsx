import { StyleSheet, Text, View } from "react-native";
import { colors, spacing } from "../theme";

const PALETTE = ["#3B82F6", "#10B981", "#F59E0B", "#8B5CF6", "#EC4899", "#14B8A6"];

type Slice = { name: string; value: number };

type Props = { title: string; data: Slice[] };

export function SimplePieChart({ title, data }: Props) {
  const filtered = data.filter((d) => d.value > 0);
  const total = filtered.reduce((s, d) => s + d.value, 0);
  if (total <= 0) {
    return (
      <View style={styles.box}>
        <Text style={styles.title}>{title}</Text>
        <Text style={styles.empty}>No data</Text>
      </View>
    );
  }

  return (
    <View style={styles.box}>
      <Text style={styles.title}>{title}</Text>
      <View style={styles.barTrack}>
        {filtered.map((slice, i) => {
          const pct = (slice.value / total) * 100;
          return (
            <View
              key={slice.name}
              style={[
                styles.barSeg,
                {
                  width: `${pct}%`,
                  backgroundColor: PALETTE[i % PALETTE.length],
                },
              ]}
            />
          );
        })}
      </View>
      {filtered.map((slice, i) => {
        const pct = (slice.value / total) * 100;
        return (
          <View key={slice.name} style={styles.legendRow}>
            <View
              style={[styles.dot, { backgroundColor: PALETTE[i % PALETTE.length] }]}
            />
            <Text style={styles.legendText}>
              {slice.name} — €{slice.value.toLocaleString("en-US", { maximumFractionDigits: 0 })} (
              {pct.toFixed(1)}%)
            </Text>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  box: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.md,
  },
  title: { color: colors.text, fontWeight: "700", fontSize: 16, marginBottom: spacing.sm },
  empty: { color: colors.textMuted },
  barTrack: {
    flexDirection: "row",
    height: 14,
    borderRadius: 7,
    overflow: "hidden",
    marginBottom: spacing.md,
  },
  barSeg: { height: "100%" },
  legendRow: { flexDirection: "row", alignItems: "center", marginBottom: 4 },
  dot: { width: 10, height: 10, borderRadius: 5, marginRight: 8 },
  legendText: { color: colors.text, fontSize: 12, flex: 1 },
});
