/**
 * Universal Logger for Browser and Node.js Environments
 *
 * This logger automatically adapts based on the runtime environment:
 * - Browser (development): Logs to console
 * - Browser (production): Silent (or can be configured for remote logging)
 * - Node.js (SSR/tests): Writes to file system
 *
 * Pattern based on auth-logger.ts which correctly avoids node: imports.
 *
 * Usage:
 *   import { createLogger } from "@/lib/logger";
 *   const logger = createLogger("subscription");
 *   await logger.log("checkout_initiated", { plan: "pro" });
 */

const isNodeRuntime =
  typeof process !== "undefined" && !!process.versions?.node;

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

  /**
   * Configure the logger (Node.js only)
   * @param filePath - Path to log file
   */
  configure?(filePath: string): void;
}

/**
 * Create a logger instance for a specific feature/module
 *
 * @param name - Logger name (used for console prefix and filename)
 * @param defaultLogPath - Default log file path for Node.js (e.g., "logs/subscription.log")
 * @returns Logger instance
 */
export function createLogger(name: string, defaultLogPath?: string): Logger {
  let configuredFilePath: string | null = defaultLogPath ?? null;

  // Browser implementation
  if (!isNodeRuntime) {
    return {
      async log(event: string, data?: unknown): Promise<void> {
        if (import.meta.env.DEV) {
          console.log(`[${name}] ${event}`, data ?? "");
        }
        // Production: Could send to remote logging service
        // Example: await sendToSentry({ event, data });
      },
    };
  }

  // Node.js implementation
  return {
    async log(event: string, data?: unknown): Promise<void> {
      if (!configuredFilePath) {
        console.log(`[${name}] ${event}`, data ?? "");
        return;
      }

      const entry: LogEntry = {
        timestamp: new Date().toISOString(),
        event,
        ...(data as Record<string, unknown>),
      };

      try {
        const fs = await import("node:fs/promises");
        const path = await import("node:path");
        const logDir = path.dirname(configuredFilePath);

        // Ensure log directory exists
        await fs.mkdir(logDir, { recursive: true });

        // Append log entry
        await fs.appendFile(configuredFilePath, JSON.stringify(entry) + "\n", {
          encoding: "utf8",
        });
      } catch (error) {
        console.error(
          `[${name}] Failed to write to ${configuredFilePath}:`,
          error
        );
      }
    },

    configure(filePath: string): void {
      configuredFilePath = filePath;
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
