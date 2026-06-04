/**
 * Writes src/lib/firebaseConfig.ts from EXPO_PUBLIC_FIREBASE_* env vars.
 * Run: node scripts/generate-firebase-config.js (from mobile/)
 */
const fs = require("fs");
const path = require("path");

const required = [
  "EXPO_PUBLIC_FIREBASE_API_KEY",
  "EXPO_PUBLIC_FIREBASE_AUTH_DOMAIN",
  "EXPO_PUBLIC_FIREBASE_PROJECT_ID",
  "EXPO_PUBLIC_FIREBASE_STORAGE_BUCKET",
  "EXPO_PUBLIC_FIREBASE_MESSAGING_SENDER_ID",
  "EXPO_PUBLIC_FIREBASE_APP_ID",
];

const missing = required.filter((k) => !process.env[k]);
if (missing.length) {
  console.error("Missing env:", missing.join(", "));
  process.exit(1);
}

const config = {
  apiKey: process.env.EXPO_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.EXPO_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.EXPO_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.EXPO_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.EXPO_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.EXPO_PUBLIC_FIREBASE_APP_ID,
};

const out = `/** Auto-generated — do not edit. Run: node scripts/generate-firebase-config.js */
export const firebaseConfig = ${JSON.stringify(config, null, 2)} as const;
`;

const target = path.join(__dirname, "..", "src", "lib", "firebaseConfig.ts");
fs.writeFileSync(target, out);
console.log("Wrote", target);
