/**
 * Universal Logger for Browser Environments
 *
 * This logger works in browser environments only:
 * - Development: Logs to console
 * - Production: Silent (or can be configured for remote logging)
 *
 * Pattern based on auth-logger.ts - browser-safe, no Node.js dependencies.
 *
 * Usage:
 *   import { createLogger } from "@/lib/logger";
 *   const logger = createLogger("subscription");
 *   await logger.log("checkout_initiated", { plan: "pro" });
 */

export interface LogEntry {
  timestamp: string;
  event: string;
  [key: string]: unknown;
}

export interface Logger {
  /**
   * Log an event with associated data
   * @param event - Event name/type
   * @param data - Event data to log
   */
  log(event: string, data?: unknown): Promise<void>;
}

/**
 * Create a logger instance for a specific feature/module
 *
 * @param name - Logger name (used for console prefix)
 * @returns Logger instance
 */
export function createLogger(name: string): Logger {
  return {
    async log(event: string, data?: unknown): Promise<void> {
      // Development: Console logging
      if (import.meta.env.DEV) {
        console.log(`[${name}] ${event}`, data ?? "");
      }

      // Production: Could send to remote logging service
      // Example: await sendToSentry({ event, data });
      // For now, silent in production
    },
  };
}

/**
 * Synchronous log for cases where async is not possible
 * Only works in browser (uses console)
 *
 * @param name - Logger name
 * @param event - Event name
 * @param data - Event data
 */
export function logSync(name: string, event: string, data?: unknown): void {
  if (typeof window !== "undefined" && import.meta.env.DEV) {
    console.log(`[${name}] ${event}`, data ?? "");
  }
}
