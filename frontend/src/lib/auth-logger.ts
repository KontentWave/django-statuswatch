/**
 * Authentication and Navigation Logger
 *
 * Logs authentication-related events to help debug login/logout flows,
 * token storage, and navigation after authentication.
 *
 * This complements backend authentication.log with client-side events.
 */

type AuthEventType =
  | "LOGIN_ATTEMPT"
  | "LOGIN_SUCCESS"
  | "LOGIN_FAILED"
  | "LOGOUT"
  | "TOKEN_STORED"
  | "TOKEN_CLEARED"
  | "NAVIGATION_TO_DASHBOARD"
  | "NAVIGATION_TO_LOGIN"
  | "NAVIGATION_BLOCKED"
  | "MULTIPLE_TENANTS_FOUND"
  | "TENANT_SELECTED"
  | "TENANT_LOGIN_FAILED"
  | "TENANT_SELECTOR_CANCELLED"
  | "TENANT_TRANSFER_INITIATED"
  | "TENANT_TRANSFER_APPLIED"
  | "TENANT_TRANSFER_FAILED"
  | "TENANT_TRANSFER_SKIPPED";

interface AuthLogEntry {
  timestamp: string;
  event: AuthEventType;
  details?: Record<string, unknown>;
  url?: string;
  username?: string;
  error?: string;
}

/**
 * Log authentication event to browser console (development mode)
 * and to localStorage for debugging
 */
export function logAuthEvent(
  event: AuthEventType,
  details?: Record<string, unknown>
): void {
  const entry: AuthLogEntry = {
    timestamp: new Date().toISOString(),
    event,
    url: window.location.href,
    ...details,
  };

  // Console logging in development
  if (import.meta.env.DEV) {
    const style = getEventStyle(event);
    console.log(`%c[AUTH] ${event}`, style, {
      ...entry,
      details,
    });
  }

  // Store recent events in localStorage for debugging (max 50 entries)
  try {
    const storageKey = "auth_debug_log";
    const existing = JSON.parse(
      localStorage.getItem(storageKey) ?? "[]"
    ) as AuthLogEntry[];
    existing.push(entry);

    // Keep only last 50 entries
    const recentEntries = existing.slice(-50);
    localStorage.setItem(storageKey, JSON.stringify(recentEntries));
  } catch (error) {
    // Fail silently if localStorage is not available
    console.warn("Failed to store auth log entry:", error);
  }
}

/**
 * Get CSS style for different event types (for console.log formatting)
 */
function getEventStyle(event: AuthEventType): string {
  switch (event) {
    case "LOGIN_SUCCESS":
    case "TOKEN_STORED":
    case "NAVIGATION_TO_DASHBOARD":
    case "TENANT_SELECTED":
    case "TENANT_TRANSFER_APPLIED":
      return "color: #10b981; font-weight: bold;"; // green
    case "LOGIN_FAILED":
    case "NAVIGATION_BLOCKED":
    case "TENANT_LOGIN_FAILED":
    case "TENANT_TRANSFER_FAILED":
      return "color: #ef4444; font-weight: bold;"; // red
    case "LOGOUT":
    case "TOKEN_CLEARED":
    case "TENANT_SELECTOR_CANCELLED":
    case "TENANT_TRANSFER_INITIATED":
    case "TENANT_TRANSFER_SKIPPED":
      return "color: #f59e0b; font-weight: bold;"; // orange
    case "LOGIN_ATTEMPT":
    case "NAVIGATION_TO_LOGIN":
    case "MULTIPLE_TENANTS_FOUND":
      return "color: #3b82f6; font-weight: bold;"; // blue
    default:
      return "color: #6b7280; font-weight: bold;"; // gray
  }
}

/**
 * Clear authentication debug logs from localStorage
 */
export function clearAuthLogs(): void {
  try {
    localStorage.removeItem("auth_debug_log");
    console.log(
      "%c[AUTH] Debug logs cleared",
      "color: #6b7280; font-weight: bold;"
    );
  } catch (error) {
    console.warn("Failed to clear auth logs:", error);
  }
}

/**
 * Get all authentication debug logs from localStorage
 */
export function getAuthLogs(): AuthLogEntry[] {
  try {
    const storageKey = "auth_debug_log";
    return JSON.parse(
      localStorage.getItem(storageKey) ?? "[]"
    ) as AuthLogEntry[];
  } catch (error) {
    console.warn("Failed to retrieve auth logs:", error);
    return [];
  }
}
