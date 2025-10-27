const isNodeRuntime =
  typeof process !== "undefined" && !!process.versions?.node;
const DEFAULT_LOG_PATH = "logs/billing-events.log";

interface BillingLogger {
  write(entry: BillingLogEntry): Promise<void>;
}

type BillingEvent = "checkout" | "config" | "portal" | "cancellation";

type BillingPhase = "start" | "success" | "error" | "completed" | "canceled";

export interface BillingLogEntry {
  timestamp: string;
  event: BillingEvent;
  phase: BillingPhase;
  plan: string;
  message?: string;
  redirectUrl?: string;
  sessionId?: string;
  source?: string;
  [key: string]: unknown;
}

interface BillingLoggerConfiguration {
  filePath?: string;
}

let activeLogger: BillingLogger = createConsoleLogger();
let configuredFilePath: string | null = null;

export function configureBillingLogger(
  options: BillingLoggerConfiguration
): void {
  const { filePath } = options;
  configuredFilePath = filePath ?? null;

  if (!isNodeRuntime || !filePath) {
    activeLogger = createConsoleLogger();
    return;
  }

  activeLogger = createFileLogger(filePath);
}

export function resetBillingLogger(): void {
  activeLogger = createConsoleLogger();
  configuredFilePath = null;
}

export async function logBillingEvent(
  entry: Omit<BillingLogEntry, "timestamp">
): Promise<void> {
  const payload: BillingLogEntry = {
    ...(entry as BillingLogEntry),
    timestamp: new Date().toISOString(),
  };

  try {
    await activeLogger.write(payload);
  } catch (error) {
    if (configuredFilePath) {
      const details =
        error instanceof Error ? `${error.name}: ${error.message}` : `${error}`;
      console.error(
        "[billing] failed to write log",
        configuredFilePath,
        details
      );
    } else {
      console.debug("[billing]", payload);
    }
  }
}

function createConsoleLogger(): BillingLogger {
  return {
    async write(entry) {
      console.debug("[billing]", entry);
    },
  };
}

function createFileLogger(filePath: string): BillingLogger {
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
  configureBillingLogger({ filePath: DEFAULT_LOG_PATH });
}
