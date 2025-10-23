import type { AxiosError } from "axios";

const isNodeRuntime =
  typeof process !== "undefined" && !!process.versions?.node;

interface EndpointLogger {
  write(entry: EndpointLogEntry): Promise<void>;
}

export interface EndpointLogEntry {
  timestamp: string;
  action: EndpointAction;
  phase: EndpointPhase;
  message?: string;
  requestId?: string;
  endpointId?: string;
  httpStatus?: number;
  errorName?: string;
  errorMessage?: string;
  payload?: unknown;
  [key: string]: unknown;
}

type EndpointAction = "list" | "create" | "delete";
type EndpointPhase = "start" | "success" | "error";

interface LoggerConfiguration {
  filePath?: string;
}

let activeLogger: EndpointLogger = createConsoleLogger();
let configuredFilePath: string | null = null;

export function configureEndpointLogger(options: LoggerConfiguration): void {
  const { filePath } = options;
  configuredFilePath = filePath ?? null;

  if (!isNodeRuntime || !filePath) {
    activeLogger = createConsoleLogger();
    return;
  }

  activeLogger = createFileLogger(filePath);
}

export function resetEndpointLogger(): void {
  activeLogger = createConsoleLogger();
  configuredFilePath = null;
}

export async function logEndpointEvent(
  entry: Omit<EndpointLogEntry, "timestamp">
): Promise<void> {
  const payload: EndpointLogEntry = {
    timestamp: new Date().toISOString(),
    ...entry,
  };

  try {
    await activeLogger.write(payload);
  } catch (error) {
    // Fallback to console if file logging fails.
    if (configuredFilePath) {
      const details =
        error instanceof Error ? `${error.name}: ${error.message}` : `${error}`;
      console.error(
        "[endpoint-client] failed to write log",
        configuredFilePath,
        details
      );
    } else {
      console.debug("[endpoint-client]", payload);
    }
  }
}

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

function createConsoleLogger(): EndpointLogger {
  return {
    async write(entry) {
      console.debug("[endpoint-client]", entry);
    },
  };
}

function createFileLogger(filePath: string): EndpointLogger {
  return {
    async write(entry) {
      const fs = await import("node:fs/promises");
      const line = `${JSON.stringify(entry)}\n`;
      await fs.appendFile(filePath, line, { encoding: "utf8" });
    },
  };
}

function isAxiosError(error: unknown): error is AxiosError {
  return (
    typeof error === "object" &&
    error !== null &&
    "isAxiosError" in error &&
    Boolean((error as AxiosError).isAxiosError)
  );
}
