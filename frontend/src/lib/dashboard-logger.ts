const isNodeRuntime =
  typeof process !== "undefined" && !!process.versions?.node;
const DEFAULT_LOG_PATH = "logs/dashboard-events.log";

interface DashboardLogger {
  write(entry: DashboardLogEntry): Promise<void>;
}

type DashboardEvent = "pagination" | "sorting";

type DashboardPhase = "start" | "success" | "error";

export interface DashboardLogEntry {
  timestamp: string;
  event: DashboardEvent;
  phase: DashboardPhase;
  page?: number;
  pageSize?: number;
  sortBy?: string;
  sortDirection?: "asc" | "desc";
  message?: string;
  [key: string]: unknown;
}

interface DashboardLoggerConfiguration {
  filePath?: string;
}

let activeLogger: DashboardLogger = createConsoleLogger();
let configuredFilePath: string | null = null;

export function configureDashboardLogger(
  options: DashboardLoggerConfiguration
): void {
  const { filePath } = options;
  configuredFilePath = filePath ?? null;

  if (!isNodeRuntime || !filePath) {
    activeLogger = createConsoleLogger();
    return;
  }

  activeLogger = createFileLogger(filePath);
}

export function resetDashboardLogger(): void {
  activeLogger = createConsoleLogger();
  configuredFilePath = null;
}

export async function logDashboardEvent(
  entry: Omit<DashboardLogEntry, "timestamp">
): Promise<void> {
  const payload: DashboardLogEntry = {
    ...(entry as DashboardLogEntry),
    timestamp: new Date().toISOString(),
  };

  try {
    await activeLogger.write(payload);
  } catch (error) {
    if (configuredFilePath) {
      const details =
        error instanceof Error ? `${error.name}: ${error.message}` : `${error}`;
      console.error(
        "[dashboard] failed to write log",
        configuredFilePath,
        details
      );
    } else {
      console.debug("[dashboard]", payload);
    }
  }
}

function createConsoleLogger(): DashboardLogger {
  return {
    async write(entry) {
      console.debug("[dashboard]", entry);
    },
  };
}

function createFileLogger(filePath: string): DashboardLogger {
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
  configureDashboardLogger({ filePath: DEFAULT_LOG_PATH });
}
