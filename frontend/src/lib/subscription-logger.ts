/**
 * Subscription Logger
 *
 * Logs subscription-related events (gating, plan changes, state transitions).
 * This logger is used across the application to track subscription lifecycle.
 *
 * Refactored to use universal logger pattern (browser-safe, no node: imports).
 */

import { createLogger, type Logger } from "./logger";

type SubscriptionEvent = "gating" | "plan_change";

type SubscriptionAction =
  | "limit_reached"
  | "cta_click"
  | "dismiss"
  | "hydrate"
  | "refresh_start"
  | "refresh_success"
  | "refresh_error"
  | "state_change"
  | "state_detected";

export interface SubscriptionLogEntry {
  event: SubscriptionEvent;
  action: SubscriptionAction;
  plan?: string;
  source?: string;
  totalCount?: number;
  limit?: number;
  message?: string;
  [key: string]: unknown;
}

const logger: Logger = createLogger(
  "subscription",
  "logs/subscription-events.log"
);

/**
 * Log a subscription event
 *
 * @param entry - Subscription log entry (timestamp added automatically by logger)
 */
export async function logSubscriptionEvent(
  entry: SubscriptionLogEntry
): Promise<void> {
  const eventName = `${entry.event}:${entry.action}`;
  await logger.log(eventName, entry);
}
