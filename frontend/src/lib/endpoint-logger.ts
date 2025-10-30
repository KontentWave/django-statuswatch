/**
 * Endpoint Logger
 *
 * Logs endpoint-related events (list, create, delete operations).
 * Refactored to use universal logger pattern (browser-safe, no node: imports).
 */

import type { AxiosError } from "axios";
import { createLogger, type Logger } from "./logger";

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
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  options: string | { filePath: string }
): void {
  // Browser logger doesn't support file configuration, but keep API for compatibility
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
