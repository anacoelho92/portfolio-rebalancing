import { StyleSheet, View, type ViewProps } from "react-native";
import { colors, spacing } from "../../theme";

type Props = ViewProps & {
  children: React.ReactNode;
  style?: ViewProps["style"];
};

export function Card({ children, style, ...rest }: Props) {
  return (
    <View style={[styles.card, style]} {...rest}>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
});
