import {
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signOut as firebaseSignOut,
  type User,
} from "firebase/auth";
import { getFirebaseAuth } from "../lib/firebase";

/** Rows in Firestore use `username` (e.g. admin). Map from Firebase Auth email. */
export function portfolioUsername(user: User | null): string {
  if (!user) return "";
  const explicit = process.env.EXPO_PUBLIC_PORTFOLIO_USERNAME?.trim();
  if (explicit) return explicit;
  const email = user.email ?? "";
  const local = email.split("@")[0]?.trim();
  return local || "admin";
}

export async function signIn(email: string, password: string) {
  const cred = await signInWithEmailAndPassword(getFirebaseAuth(), email, password);
  return {
    name: cred.user.displayName ?? portfolioUsername(cred.user),
    username: portfolioUsername(cred.user),
    email: cred.user.email ?? email,
  };
}

export async function signOut() {
  await firebaseSignOut(getFirebaseAuth());
}

export function subscribeAuth(cb: (user: User | null) => void) {
  return onAuthStateChanged(getFirebaseAuth(), cb);
}

export function currentUser() {
  return getFirebaseAuth().currentUser;
}
