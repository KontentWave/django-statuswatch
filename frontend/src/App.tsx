import { useEffect } from "react";
import Providers from "@/app/providers";
import { AppRouter } from "@/app/router";
import { api } from "@/lib/api";

/**
 * Check if we're on a subdomain (potential tenant)
 */
function hasSubdomain(): boolean {
  const hostname = window.location.hostname;
  return hostname !== "localhost" && hostname !== "127.0.0.1";
}

/**
 * Get the public (root) domain from current hostname
 * Examples:
 *   acme.statuswatch.kontentwave.digital → statuswatch.kontentwave.digital
 *   tenant.localhost → localhost
 */
function getPublicDomain(): string {
  const hostname = window.location.hostname;

  // For localhost development
  if (hostname === "localhost" || hostname === "127.0.0.1") {
    return hostname;
  }

  // For production: strip the first subdomain part
  const parts = hostname.split(".");

  // If we have a subdomain (e.g., acme.statuswatch.kontentwave.digital)
  // Remove the first part to get the public domain (statuswatch.kontentwave.digital)
  if (parts.length >= 2) {
    return parts.slice(1).join(".");
  }

  // Fallback: return as-is (shouldn't happen in practice)
  return hostname;
}

/**
 * Validate tenant subdomain exists, redirect to public domain if not
 */
async function validateTenantSubdomain() {
  if (!hasSubdomain()) {
    return; // On public domain, no validation needed
  }

  try {
    // Try to ping the API - invalid tenants will fail
    await api.get("/ping/");
    // If successful, tenant exists - continue normally
  } catch {
    // Invalid tenant subdomain - redirect to public domain
    console.warn(
      "Invalid tenant subdomain detected, redirecting to public domain"
    );
    const publicDomain = getPublicDomain();
    const port = window.location.port ? `:${window.location.port}` : "";
    window.location.href = `${window.location.protocol}//${publicDomain}${port}/`;
  }
}

export default function App() {
  useEffect(() => {
    validateTenantSubdomain();
  }, []);

  return (
    <Providers>
      <AppRouter />
    </Providers>
  );
}
