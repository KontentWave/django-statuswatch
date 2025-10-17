// frontend/src/lib/env.ts

// Prefer explicit env overrides when provided.
// 1) VITE_API_BASE (full base incl. scheme/host, no trailing /), e.g. https://acme.statuswatch.local
// 2) VITE_BACKEND_ORIGIN (scheme/host only), we'll append /api
// 3) Fallback to window.location.origin in browser, or http://localhost:8011 for SSR/tools.
const EXPLICIT = (import.meta.env?.VITE_API_BASE as string | undefined)?.replace(/\/$/, "");
const ORIGIN =
  EXPLICIT ??
  (import.meta.env?.VITE_BACKEND_ORIGIN as string | undefined) ??
  (typeof window !== "undefined" ? window.location.origin : "http://localhost:8011");

export const API_BASE = `${ORIGIN}/api`;

export const apiUrl = (path: string) =>
  `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;

export const STRIPE_PUBLIC_KEY =
  (import.meta.env?.VITE_STRIPE_PUBLIC_KEY as string | undefined) ?? "";
