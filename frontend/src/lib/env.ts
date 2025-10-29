// frontend/src/lib/env.ts
import { debug } from "./debug";

// For multi-tenant setup with Vite proxy:
// - Frontend serves on the subdomain: http://{tenant}.localhost:5173
// - API calls go to /api (same origin)
// - Vite proxy forwards to: http://{tenant}.localhost:8001
//
// The proxy configuration in vite.config.ts handles the tenant routing.
// Frontend just needs to use window.location.origin for the API base.

// Prefer explicit env overrides when provided.
// 1) VITE_API_BASE (full base incl. scheme/host, no trailing /), e.g. https://acme.statuswatch.local
// 2) VITE_BACKEND_ORIGIN (scheme/host only), we'll append /api
// 3) Fallback to window.location.origin (same origin as frontend, Vite proxies /api)
const EXPLICIT = (
  import.meta.env?.VITE_API_BASE as string | undefined
)?.replace(/\/$/, "");
const ORIGIN =
  EXPLICIT ??
  (import.meta.env?.VITE_BACKEND_ORIGIN as string | undefined) ??
  (typeof window !== "undefined"
    ? window.location.origin
    : "http://localhost:8011");

export const API_BASE = `${ORIGIN}/api`;

// Debug logging (only in development)
if (typeof window !== "undefined") {
  debug("🔧 API Configuration:", {
    VITE_API_BASE: import.meta.env?.VITE_API_BASE,
    VITE_BACKEND_ORIGIN: import.meta.env?.VITE_BACKEND_ORIGIN,
    "window.location.origin": window.location.origin,
    "window.location.hostname": window.location.hostname,
    COMPUTED_ORIGIN: ORIGIN,
    FINAL_API_BASE: API_BASE,
    note: "API calls use Vite proxy - requests to /api are forwarded to backend",
  });
}

export const apiUrl = (path: string) =>
  `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;

export const STRIPE_PUBLIC_KEY =
  (import.meta.env?.VITE_STRIPE_PUBLIC_KEY as string | undefined) ?? "";
