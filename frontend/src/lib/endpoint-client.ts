import type { AxiosError } from "axios";

import { api } from "./api";
import { logEndpointEvent, serializeAxiosError } from "./endpoint-logger";

type UUID = string;

type MaybeNull<T> = T | null;

export interface EndpointDto {
  id: UUID;
  name: string;
  url: string;
  interval_minutes: number;
  last_status: string;
  last_checked_at: MaybeNull<string>;
  last_latency_ms: MaybeNull<number>;
  last_enqueued_at: MaybeNull<string>;
  created_at: string;
  updated_at: string;
}

export interface EndpointListResponse {
  count: number;
  next: MaybeNull<string>;
  previous: MaybeNull<string>;
  results: EndpointDto[];
}

export interface EndpointListParams {
  page?: number;
}

export interface CreateEndpointRequest {
  name?: string;
  url: string;
  interval_minutes: number;
}

export interface DeleteEndpointResult {
  endpointId: UUID;
}

export async function listEndpoints(
  params: EndpointListParams = {}
): Promise<EndpointListResponse> {
  const requestId = generateRequestId();
  await logEndpointEvent({ action: "list", phase: "start", requestId, params });

  try {
    const { data } = await api.get<EndpointListResponse>("/endpoints/", {
      params: omitUndefined(params),
    });
    await logEndpointEvent({
      action: "list",
      phase: "success",
      requestId,
      endpointCount: data.count,
      params,
    });
    return data;
  } catch (error) {
    await logEndpointEvent({
      action: "list",
      phase: "error",
      requestId,
      params,
      ...serializeAxiosError(error as AxiosError | Error),
    });
    throw error;
  }
}

export async function createEndpoint(
  payload: CreateEndpointRequest
): Promise<EndpointDto> {
  const requestId = generateRequestId();
  await logEndpointEvent({
    action: "create",
    phase: "start",
    requestId,
    payload,
  });

  try {
    const { data } = await api.post<EndpointDto>("/endpoints/", payload);
    await logEndpointEvent({
      action: "create",
      phase: "success",
      requestId,
      endpointId: data.id,
    });
    return data;
  } catch (error) {
    await logEndpointEvent({
      action: "create",
      phase: "error",
      requestId,
      payload,
      ...serializeAxiosError(error as AxiosError | Error),
    });
    throw error;
  }
}

export async function deleteEndpoint(
  endpointId: UUID
): Promise<DeleteEndpointResult> {
  const requestId = generateRequestId();
  await logEndpointEvent({
    action: "delete",
    phase: "start",
    requestId,
    endpointId,
  });

  try {
    await api.delete(`/endpoints/${endpointId}/`);
    await logEndpointEvent({
      action: "delete",
      phase: "success",
      requestId,
      endpointId,
    });
    return { endpointId };
  } catch (error) {
    await logEndpointEvent({
      action: "delete",
      phase: "error",
      requestId,
      endpointId,
      ...serializeAxiosError(error as AxiosError | Error),
    });
    throw error;
  }
}

function generateRequestId(): string {
  const globalCrypto = typeof crypto !== "undefined" ? crypto : undefined;
  if (globalCrypto && "randomUUID" in globalCrypto) {
    return globalCrypto.randomUUID();
  }
  return `req-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}

function omitUndefined<T extends EndpointListParams | Record<string, unknown>>(
  input: T
): T {
  return Object.fromEntries(
    Object.entries(input).filter(([, value]) => value !== undefined)
  ) as T;
}
