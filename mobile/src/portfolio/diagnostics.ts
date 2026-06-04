import type { MasterRow } from "./core";

export function distinctUsernames(rows: MasterRow[]): string[] {
  const seen = new Set<string>();
  for (const r of rows) {
    const u = String(r.username ?? "").trim();
    if (u) seen.add(u);
  }
  return [...seen].sort();
}

export function emptyDataMessage(
  totalRows: number,
  configuredUsername: string,
  usernames: string[]
): string {
  if (totalRows === 0) {
    return (
      "Firestore has no portfolio rows yet. On your Mac: add a Firebase service account " +
      "to .env (not the web apiKey snippet), then run:\n" +
      "python scripts/migrate_gsheets_to_firestore.py"
    );
  }
  if (!usernames.includes(configuredUsername)) {
    const list = usernames.length ? usernames.join(", ") : "(no username column)";
    return (
      `Firestore has ${totalRows} rows for: ${list}. ` +
      `The app filters by "${configuredUsername}". ` +
      `Set EXPO_PUBLIC_PORTFOLIO_USERNAME in mobile/.env to match.`
    );
  }
  return "No portfolios found for this account.";
}
