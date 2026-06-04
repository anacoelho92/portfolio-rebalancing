import { StyleSheet, Text, View } from "react-native";
import { colors, spacing } from "../../theme";

type Props = {
  title: string;
};

export function SectionHeader({ title }: Props) {
  return (
    <View style={styles.wrap}>
      <Text style={styles.title}>{title}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginBottom: spacing.md, marginTop: spacing.sm },
  title: {
    color: colors.text,
    fontSize: 18,
    fontWeight: "700",
  },
});
