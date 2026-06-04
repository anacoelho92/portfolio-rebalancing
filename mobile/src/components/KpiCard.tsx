import { StyleSheet, Text, View } from "react-native";
import { colors, spacing } from "../theme";

type Props = {
  label: string;
  value: string;
  subValue?: string;
  accent?: boolean;
  compact?: boolean;
  tone?: "positive" | "negative";
};

export function KpiCard({
  label,
  value,
  subValue,
  accent,
  compact,
  tone,
}: Props) {
  const valueColor =
    tone === "positive"
      ? colors.accent
      : tone === "negative"
        ? colors.danger
        : accent
          ? colors.accent
          : colors.text;

  return (
    <View style={[styles.card, compact && styles.cardCompact]}>
      <Text
        style={[styles.label, compact && styles.labelCompact]}
        numberOfLines={2}
      >
        {label}
      </Text>
      <Text
        style={[styles.value, compact && styles.valueCompact, { color: valueColor }]}
        numberOfLines={1}
        adjustsFontSizeToFit
        minimumFontScale={compact ? 0.65 : 0.75}
      >
        {value}
      </Text>
      {subValue ? (
        <Text
          style={[styles.subValue, { color: valueColor }]}
          numberOfLines={1}
          adjustsFontSizeToFit
          minimumFontScale={0.75}
        >
          {subValue}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flex: 1,
    minWidth: "45%",
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  cardCompact: {
    flex: 1,
    minWidth: 0,
    padding: spacing.sm,
    borderRadius: 10,
  },
  label: {
    color: colors.text,
    fontSize: 12,
    marginBottom: spacing.xs,
    opacity: 0.85,
  },
  labelCompact: {
    fontSize: 10,
    marginBottom: 2,
  },
  value: {
    color: colors.text,
    fontSize: 18,
    fontWeight: "700",
  },
  valueCompact: {
    fontSize: 15,
  },
  subValue: {
    fontSize: 12,
    fontWeight: "600",
    marginTop: 2,
    opacity: 0.9,
  },
});
