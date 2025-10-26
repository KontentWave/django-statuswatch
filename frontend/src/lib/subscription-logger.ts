const isNodeRuntime =
  typeof process !== "undefined" && !!process.versions?.node;

const DEFAULT_LOG_PATH = "logs/subscription-events.log";

interface SubscriptionLogger {
  write(entry: SubscriptionLogEntry): Promise<void>;
}

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
  timestamp: string;
  event: SubscriptionEvent;
  action: SubscriptionAction;
  plan?: string;
  source?: string;
  totalCount?: number;
  limit?: number;
  message?: string;
  [key: string]: unknown;
}

interface SubscriptionLoggerConfiguration {
  filePath?: string;
}

let activeLogger: SubscriptionLogger = createConsoleLogger();
let configuredFilePath: string | null = null;

export function configureSubscriptionLogger(
  options: SubscriptionLoggerConfiguration
): void {
  const { filePath } = options;
  configuredFilePath = filePath ?? null;

  if (!isNodeRuntime || !filePath) {
    activeLogger = createConsoleLogger();
    return;
  }

  activeLogger = createFileLogger(filePath);
}

export function resetSubscriptionLogger(): void {
  activeLogger = createConsoleLogger();
  configuredFilePath = null;
}

export async function logSubscriptionEvent(
  entry: Omit<SubscriptionLogEntry, "timestamp">
): Promise<void> {
  const payload: SubscriptionLogEntry = {
    ...(entry as SubscriptionLogEntry),
    timestamp: new Date().toISOString(),
  };

  try {
    await activeLogger.write(payload);
  } catch (error) {
    if (configuredFilePath) {
      const details =
        error instanceof Error ? `${error.name}: ${error.message}` : `${error}`;
      console.error(
        "[subscription] failed to write log",
        configuredFilePath,
        details
      );
    } else {
      console.debug("[subscription]", payload);
    }
  }
}

function createConsoleLogger(): SubscriptionLogger {
  return {
    async write(entry) {
      console.debug("[subscription]", entry);
    },
  };
}

function createFileLogger(filePath: string): SubscriptionLogger {
  return {
    async write(entry) {
      const fs = await import("node:fs/promises");
      const path = await import("node:path");
      await fs.mkdir(path.dirname(filePath), { recursive: true });
      await fs.appendFile(filePath, `${JSON.stringify(entry)}\n`, {
        encoding: "utf8",
      });
    },
  };
}

if (isNodeRuntime) {
  configureSubscriptionLogger({ filePath: DEFAULT_LOG_PATH });
}
