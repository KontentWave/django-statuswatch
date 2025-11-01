import { logAuthEvent } from "@/lib/auth-logger";

type TransferSource = "login_page" | "tenant_selector" | "homepage_demo";

interface TenantSessionTransferParams {
  accessToken: string;
  refreshToken?: string | null;
  tenantDomain: string;
  tenantName?: string | null;
  tenantSchema?: string | null;
  username?: string | null;
  source: TransferSource;
}

function extractHostAndPort(domain: string): { host: string; port: string } {
  if (!domain) {
    return { host: "", port: "" };
  }

  // Allow full URLs or bare host[:port]
  try {
    if (/^https?:\/\//i.test(domain)) {
      const parsed = new URL(domain);
      return { host: parsed.hostname, port: parsed.port };
    }
  } catch (error) {
    console.warn("Failed to parse tenant domain as URL", { domain, error });
  }

  const [host, port = ""] = domain.split(":", 2);
  return { host, port };
}

function encodePayload(payload: Record<string, unknown>): string {
  const json = JSON.stringify(payload);
  return btoa(json);
}

export function initiateTenantSessionTransfer(
  params: TenantSessionTransferParams
): boolean {
  if (typeof window === "undefined") {
    return false;
  }

  const {
    accessToken,
    refreshToken,
    tenantDomain,
    tenantName,
    tenantSchema,
    username,
    source,
  } = params;

  if (!accessToken || !tenantDomain) {
    return false;
  }

  const { host, port: fallbackPort } = extractHostAndPort(tenantDomain);
  if (!host) {
    return false;
  }

  const protocol = window.location.protocol || "https:";
  const currentPort = window.location.port;
  const resolvedPort = currentPort || fallbackPort || "";
  const portSegment = resolvedPort ? `:${resolvedPort}` : "";
  const tenantOrigin = `${protocol}//${host}${portSegment}`;

  if (tenantOrigin === window.location.origin) {
    logAuthEvent("TENANT_TRANSFER_SKIPPED", {
      tenant: tenantName,
      tenant_schema: tenantSchema,
      reason: "same_origin",
      destination: `${tenantOrigin}/dashboard`,
      source,
    });
    return false;
  }

  const payload = {
    access: accessToken,
    refresh: refreshToken ?? null,
    tenant_schema: tenantSchema ?? null,
    tenant_name: tenantName ?? null,
    username: username ?? null,
    issued_at: new Date().toISOString(),
    source,
  };

  const encoded = encodePayload(payload);
  const hashParams = new URLSearchParams();
  hashParams.set("session", encoded);
  hashParams.set("source", source);

  const destination = `${tenantOrigin}/login#${hashParams.toString()}`;

  logAuthEvent("TENANT_TRANSFER_INITIATED", {
    tenant: tenantName,
    tenant_schema: tenantSchema,
    destination,
    source,
  });

  logAuthEvent("NAVIGATION_TO_DASHBOARD", {
    from: source,
    username,
    destination,
    tenant: tenantName,
  });

  window.location.assign(destination);
  return true;
}
