import { useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { PieChart } from "react-native-gifted-charts";
import { chartPalette, colors, spacing } from "../theme";

export type PieSlice = { name: string; value: number };

type Props = {
  title: string;
  data: PieSlice[];
};

function formatEuro(value: number) {
  return `€${value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function DonutPieChart({ title, data }: Props) {
  const [selectedIndex, setSelectedIndex] = useState(-1);

  const filtered = useMemo(() => data.filter((d) => d.value > 0), [data]);
  const total = filtered.reduce((s, d) => s + d.value, 0);

  useEffect(() => {
    setSelectedIndex(-1);
  }, [title, data]);

  if (total <= 0) {
    return (
      <View style={styles.box}>
        <Text style={styles.title}>{title}</Text>
        <Text style={styles.empty}>No data</Text>
      </View>
    );
  }

  const pieData = filtered.map((slice, index) => ({
    value: slice.value,
    color: chartPalette[index % chartPalette.length],
  }));

  const active =
    selectedIndex >= 0 && selectedIndex < filtered.length
      ? filtered[selectedIndex]
      : null;
  const centerValue = active ? formatEuro(active.value) : formatEuro(total);
  const centerCaption = active ? active.name : "Total";

  function selectSlice(index: number) {
    setSelectedIndex((prev) => (prev === index ? -1 : index));
  }

  return (
    <View style={styles.box}>
      <Text style={styles.title}>{title}</Text>
      <View style={styles.chartWrap}>
        <PieChart
          data={pieData}
          donut
          radius={110}
          innerRadius={82}
          innerCircleColor={colors.card}
          showText={false}
          focusOnPress
          toggleFocusOnPress
          selectedIndex={selectedIndex}
          setSelectedIndex={setSelectedIndex}
          extraRadius={14}
          edgesPressable
          strokeWidth={2}
          strokeColor={colors.bg}
          centerLabelComponent={() => (
            <View style={styles.center}>
              <Text style={styles.centerCaption} numberOfLines={2}>
                {centerCaption}
              </Text>
              <Text style={styles.centerValue} numberOfLines={1} adjustsFontSizeToFit>
                {centerValue}
              </Text>
            </View>
          )}
        />
      </View>
      {filtered.map((slice, index) => {
        const color = chartPalette[index % chartPalette.length];
        const isActive = selectedIndex === index;
        return (
          <Pressable
            key={slice.name}
            style={[styles.legendRow, isActive && styles.legendRowActive]}
            onPress={() => selectSlice(index)}
          >
            <View style={[styles.dot, { backgroundColor: color }]} />
            <Text style={[styles.legendName, isActive && styles.legendNameActive]}>
              {slice.name}
            </Text>
          </Pressable>
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
  title: {
    color: colors.text,
    fontWeight: "700",
    fontSize: 17,
    textAlign: "center",
    marginBottom: spacing.sm,
  },
  empty: { color: colors.textMuted, textAlign: "center" },
  chartWrap: { alignItems: "center", marginVertical: spacing.sm },
  center: { alignItems: "center", maxWidth: 140, paddingHorizontal: spacing.xs },
  centerCaption: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: "600",
    textAlign: "center",
    marginBottom: 2,
  },
  centerValue: { color: colors.text, fontWeight: "700", fontSize: 14 },
  legendRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: spacing.sm,
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.xs,
    borderRadius: 8,
  },
  legendRowActive: {
    backgroundColor: colors.cardElevated,
  },
  dot: { width: 10, height: 10, borderRadius: 5, marginRight: spacing.sm },
  legendName: { color: colors.text, fontWeight: "600", fontSize: 14, flex: 1 },
  legendNameActive: { color: colors.accent },
});
