/**
 * Dashboard Logger
 *
 * Logs dashboard-related events (pagination, sorting).
 * Refactored to use universal logger pattern (browser-safe, no node: imports).
 */

import { createLogger, type Logger } from "./logger";

type DashboardEvent = "pagination" | "sorting";

type DashboardPhase = "start" | "success" | "error";

export interface DashboardLogEntry {
  event: DashboardEvent;
  phase: DashboardPhase;
  page?: number;
  pageSize?: number;
  sortBy?: string;
  sortDirection?: "asc" | "desc";
  message?: string;
  [key: string]: unknown;
}

const logger: Logger = createLogger("dashboard", "logs/dashboard-events.log");

/**
 * Log a dashboard event
 *
 * @param entry - Dashboard log entry (timestamp added automatically by logger)
 */
export async function logDashboardEvent(
  entry: DashboardLogEntry
): Promise<void> {
  const eventName = `${entry.event}:${entry.phase}`;
  await logger.log(eventName, entry);
}
