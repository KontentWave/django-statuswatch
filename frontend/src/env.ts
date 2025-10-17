/// <reference types="vite/client" />

// --- Centralized env + helpers ---------------------------------------------

const isBrowser = typeof window !== "undefined";

// Prefer explicit origin from env (CI/preview), otherwise use current page.
// Fallback for tests/SSR.
const rawOrigin =
  (import.meta.env?.VITE_BACKEND_ORIGIN as string | undefined) ??
  (isBrowser ? window.location.origin : "http://localhost:8011");

// Normalize: drop any trailing slashes to avoid `//api`.
export const BACKEND_ORIGIN = rawOrigin.replace(/\/+$/, "");

export const API_BASE = `${BACKEND_ORIGIN}/api` as const;

/** Build a full API URL from a path (handles leading slashes). */
export function apiUrl(path = ""): string {
  if (!path) return API_BASE;
  return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
}

/** Publishable Stripe key for client usage (may be empty in dev/CI). */
export const STRIPE_PUBLIC_KEY =
  (import.meta.env?.VITE_STRIPE_PUBLIC_KEY as string | undefined) ?? "";

/** Useful flag if you need it in UI. */
export const IS_DEV = import.meta.env?.MODE !== "production";

/** (Optional) WebSocket base URL if you add realtime later. */
export function wsBase(): string {
  const { protocol, host } = new URL(BACKEND_ORIGIN);
  const wsProto = protocol === "https:" ? "wss" : "ws";
  return `${wsProto}://${host}`;
}
