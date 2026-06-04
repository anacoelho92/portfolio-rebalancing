import { StyleSheet, Text, View } from "react-native";
import { colors, spacing } from "../../theme";

type Variant = "info" | "warning" | "success";

type Props = {
  message: string;
  variant?: Variant;
};

const variantStyles: Record<Variant, { bg: string; border: string; text: string }> = {
  info: { bg: "rgba(59, 130, 246, 0.12)", border: "rgba(59, 130, 246, 0.4)", text: "#93C5FD" },
  warning: {
    bg: "rgba(255, 139, 118, 0.1)",
    border: "rgba(255, 139, 118, 0.5)",
    text: colors.cashWarning,
  },
  success: {
    bg: "rgba(16, 185, 129, 0.12)",
    border: "rgba(16, 185, 129, 0.4)",
    text: colors.accent,
  },
};

export function InfoBanner({ message, variant = "info" }: Props) {
  const v = variantStyles[variant];
  return (
    <View style={[styles.banner, { backgroundColor: v.bg, borderColor: v.border }]}>
      <Text style={[styles.text, { color: v.text }]}>{message}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    borderRadius: 8,
    borderWidth: 1,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  text: { fontSize: 14, lineHeight: 20 },
});
