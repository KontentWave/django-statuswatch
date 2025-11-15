import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { promises as fs } from "node:fs";
import { mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import type { AxiosError } from "axios";

import {
  configureEndpointLogger,
  resetEndpointLogger,
} from "../endpoint-logger";
import {
  createEndpoint,
  deleteEndpoint,
  listEndpoints,
} from "../endpoint-client";
import type { CreateEndpointRequest } from "@/types/api";

vi.mock("../api", () => createApiDouble());

function createApiDouble() {
  return {
    api: {
      get: vi.fn(),
      post: vi.fn(),
      delete: vi.fn(),
    },
  };
}

type ApiDouble = ReturnType<typeof createApiDouble>["api"];

describe("endpoint-client", () => {
  let logDir: string;
  let logFilePath: string;
  let apiMock: ApiDouble;

  beforeEach(async () => {
    logDir = await mkdtemp(join(tmpdir(), "endpoint-client-test-"));
    logFilePath = join(logDir, "endpoint-client.log");
    configureEndpointLogger({ filePath: logFilePath });

    const module = await import("../api");
    apiMock = vi.mocked(module.api, true);
    apiMock.get.mockReset();
    apiMock.post.mockReset();
    apiMock.delete.mockReset();
  });

  afterEach(async () => {
    resetEndpointLogger();
    try {
      await fs.rm(logDir, { recursive: true, force: true });
    } catch (error) {
      // noop in case tmp cleanup fails; tests don't depend on it.
      void error;
    }
  });

  it("lists endpoints and records start/success log entries", async () => {
    const payload = {
      count: 1,
      results: [
        {
          id: "abc",
          name: "Primary API",
          url: "https://example.com/health",
          interval_minutes: 5,
          last_status: "ok",
          last_checked_at: "2025-10-22T12:00:00Z",
          last_latency_ms: 123.4,
          last_enqueued_at: "2025-10-22T12:01:00Z",
          created_at: "2025-10-22T10:00:00Z",
          updated_at: "2025-10-22T12:01:00Z",
        },
      ],
    };

    apiMock.get.mockResolvedValue({ data: payload });

    const result = await listEndpoints();

    expect(apiMock.get).toHaveBeenCalledWith("/endpoints/", { params: {} });
    expect(result).toEqual(payload);

    const logContents = await fs.readFile(logFilePath, "utf8");
    const entries = logContents
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line));

    expect(entries).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ action: "list", phase: "start", params: {} }),
        expect.objectContaining({
          action: "list",
          phase: "success",
          params: {},
        }),
      ])
    );
  });

  it("passes pagination params when provided", async () => {
    const payload = {
      count: 0,
      results: [],
    };

    apiMock.get.mockResolvedValue({ data: payload });

    const result = await listEndpoints({ page: 2 });

    expect(apiMock.get).toHaveBeenCalledWith("/endpoints/", {
      params: { page: 2 },
    });
    expect(result).toEqual(payload);

    const entries = await readLogEntries(logFilePath);
    expect(entries).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          action: "list",
          phase: "start",
          params: { page: 2 },
        }),
        expect.objectContaining({
          action: "list",
          phase: "success",
          params: { page: 2 },
        }),
      ])
    );
  });

  it("creates an endpoint and logs result", async () => {
    const request: CreateEndpointRequest = {
      name: "Billing API",
      url: "https://example.com/billing",
      interval_minutes: 15,
    };

    const response = {
      id: "endpoint-123",
      ...request,
      last_status: "pending",
      last_checked_at: null,
      last_latency_ms: null,
      last_enqueued_at: "2025-10-22T12:02:00Z",
      created_at: "2025-10-22T12:02:00Z",
      updated_at: "2025-10-22T12:02:00Z",
    };

    apiMock.post.mockResolvedValue({ data: response });

    const result = await createEndpoint(request);

    expect(apiMock.post).toHaveBeenCalledWith("/endpoints/", request);
    expect(result).toEqual(response);

    const entries = await readLogEntries(logFilePath);
    expect(entries).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ action: "create", phase: "start" }),
        expect.objectContaining({
          action: "create",
          phase: "success",
          endpointId: response.id,
        }),
      ])
    );
  });

  it("logs failure when endpoint deletion errors", async () => {
    const error = new Error("boom") as AxiosError;
    error.name = "AxiosError";

    apiMock.delete.mockRejectedValue(error);

    await expect(deleteEndpoint("endpoint-456")).rejects.toThrow(error);

    const entries = await readLogEntries(logFilePath);
    expect(entries).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          action: "delete",
          phase: "start",
          endpointId: "endpoint-456",
        }),
        expect.objectContaining({
          action: "delete",
          phase: "error",
          errorName: "AxiosError",
        }),
      ])
    );
  });
});

async function readLogEntries(filePath: string) {
  const raw = await fs.readFile(filePath, "utf8").catch(() => "");
  return raw
    .trim()
    .split("\n")
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}
