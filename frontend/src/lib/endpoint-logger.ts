/**
 * Endpoint Logger
 *
 * Logs endpoint-related events (list, create, delete operations).
 * Refactored to use universal logger pattern (browser-safe, no node: imports).
 */

import type { AxiosError } from "axios";
import { createLogger, type Logger, type LogEntry } from "./logger";

type EndpointAction = "list" | "create" | "delete";
type EndpointPhase = "start" | "success" | "error";

type EndpointLogEntryBase = {
  action: EndpointAction;
  phase: EndpointPhase;
  message?: string;
  requestId?: string;
  endpointId?: string;
  httpStatus?: number;
  errorName?: string;
  errorMessage?: string;
  payload?: unknown;
};

export type EndpointLogEntry = EndpointLogEntryBase & Record<string, unknown>;

let logger: Logger = createLogger("endpoint-client");

/**
 * Configure endpoint logger (for testing)
 * Note: Browser logger doesn't support file paths, this is a no-op for compatibility
 */
export function configureEndpointLogger(
  options: string | { filePath: string }
): void {
  const filePath = typeof options === "string" ? options : options.filePath;

  if (filePath && canUseFileLogger()) {
    logger = createFileLogger("endpoint-client", filePath);
    return;
  }

  logger = createLogger("endpoint-client");
}

/**
 * Reset endpoint logger to default (for testing)
 */
export function resetEndpointLogger(): void {
  logger = createLogger("endpoint-client");
}

/**
 * Log an endpoint event
 *
 * @param entry - Endpoint log entry (timestamp added automatically by logger)
 */
export async function logEndpointEvent(entry: EndpointLogEntry): Promise<void> {
  const eventName = `${entry.action}:${entry.phase}`;
  await logger.log(eventName, entry);
}

/**
 * Serialize Axios error for logging
 *
 * @param error - Axios or generic Error
 * @returns Structured error data
 */
export function serializeAxiosError(
  error: AxiosError | Error
): Pick<EndpointLogEntry, "errorName" | "errorMessage" | "httpStatus"> {
  const base: Pick<
    EndpointLogEntry,
    "errorName" | "errorMessage" | "httpStatus"
  > = {
    errorName: error.name || "Error",
    errorMessage: error.message,
    httpStatus: undefined,
  };

  if (isAxiosError(error)) {
    base.httpStatus = error.response?.status;
  }

  return base;
}

function isAxiosError(error: unknown): error is AxiosError {
  return (
    typeof error === "object" &&
    error !== null &&
    "isAxiosError" in error &&
    Boolean((error as AxiosError).isAxiosError)
  );
}

function canUseFileLogger(): boolean {
  if (typeof process === "undefined") {
    return false;
  }

  const isNode = Boolean(process.versions?.node);
  if (!isNode) {
    return false;
  }

  const hasTestFlag =
    process.env.VITEST === "true" || process.env.NODE_ENV === "test";

  return hasTestFlag || typeof window === "undefined";
}

function createFileLogger(name: string, filePath: string): Logger {
  let fsPromise: Promise<typeof import("node:fs/promises")> | null = null;
  let pathPromise: Promise<typeof import("node:path")> | null = null;

  async function resolveFs() {
    if (!fsPromise) {
      fsPromise = import("node:fs/promises");
    }
    return fsPromise;
  }

  async function resolvePath() {
    if (!pathPromise) {
      pathPromise = import("node:path");
    }
    return pathPromise;
  }

  return {
    async log(event: string, data?: unknown): Promise<void> {
      const [{ appendFile, mkdir }, { dirname }] = await Promise.all([
        resolveFs(),
        resolvePath(),
      ]);

      await mkdir(dirname(filePath), { recursive: true });

      const base: LogEntry = {
        timestamp: new Date().toISOString(),
        event: `[${name}] ${event}`,
        logger: name,
        pid: typeof process !== "undefined" ? process.pid : undefined,
        environment:
          typeof process !== "undefined" ? process.env.NODE_ENV : undefined,
      };
      const payload =
        data && typeof data === "object"
          ? (data as Record<string, unknown>)
          : { value: data };

      const entry = { ...base, ...payload };
      await appendFile(filePath, `${JSON.stringify(entry)}\n`, "utf8");
    },
  };
}
