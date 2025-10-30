/**
 * Billing Logger
 *
 * Logs billing-related events (checkout, portal, cancellations).
 * Refactored to use universal logger pattern (browser-safe, no node: imports).
 */

import { createLogger, type Logger } from "./logger";

type BillingEvent = "checkout" | "config" | "portal" | "cancellation";

type BillingPhase = "start" | "success" | "error" | "completed" | "canceled";

export interface BillingLogEntry {
  event: BillingEvent;
  phase: BillingPhase;
  plan: string;
  message?: string;
  redirectUrl?: string;
  sessionId?: string;
  source?: string;
  [key: string]: unknown;
}

const logger: Logger = createLogger("billing", "logs/billing-events.log");

/**
 * Log a billing event
 *
 * @param entry - Billing log entry (timestamp added automatically by logger)
 */
export async function logBillingEvent(entry: BillingLogEntry): Promise<void> {
  const eventName = `${entry.event}:${entry.phase}`;
  await logger.log(eventName, entry);
}
