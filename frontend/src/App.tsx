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
    window.location.href = `${window.location.protocol}//localhost:${window.location.port}/`;
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
