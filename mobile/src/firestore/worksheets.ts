import { doc, getDoc, setDoc, serverTimestamp } from "firebase/firestore";
import { getDb } from "../lib/firebase";

export const WORKSHEETS = [
  "Portfolios",
  "StockPurchases",
  "Dividends",
  "InvestmentLog",
] as const;

export type WorksheetName = (typeof WORKSHEETS)[number];

const SHEET_DOC_ID = "data";

export async function readWorksheetRows(
  name: WorksheetName
): Promise<Record<string, unknown>[]> {
  const snap = await getDoc(doc(getDb(), name, SHEET_DOC_ID));
  if (!snap.exists()) return [];
  const data = snap.data();
  const rows = data?.rows;
  return Array.isArray(rows) ? (rows as Record<string, unknown>[]) : [];
}

export async function writeWorksheetRows(
  name: WorksheetName,
  rows: Record<string, unknown>[]
): Promise<void> {
  await setDoc(doc(getDb(), name, SHEET_DOC_ID), {
    rows,
    updated_at: serverTimestamp(),
  });
}
