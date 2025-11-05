import { Link } from "@tanstack/react-router";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { STRIPE_PK } from "@/lib/config";
import { storeAuthTokens } from "@/lib/auth";
import { logAuthEvent } from "@/lib/auth-logger";
import { initiateTenantSessionTransfer } from "@/lib/tenant-session";

export default function Home() {
  const loginDemo = async () => {
    logAuthEvent("LOGIN_ATTEMPT", {
      username: "jwt@example.com",
      source: "homepage_demo_button",
    });

    try {
      // Use new multi-tenant login endpoint
      const { data } = await api.post("/auth/login/", {
        username: "jwt@example.com",
        password: "TestPass123!",
      });

      storeAuthTokens({ access: data.access, refresh: data.refresh });
      logAuthEvent("TOKEN_STORED", {
        username: "jwt@example.com",
        hasAccess: !!data.access,
        hasRefresh: !!data.refresh,
        tenant_schema: data.tenant_schema,
        tenant_name: data.tenant_name,
      });

      toast.success(`Logged in as jwt@example.com (${data.tenant_name})`);
      logAuthEvent("LOGIN_SUCCESS", {
        username: "jwt@example.com",
        tenant: data.tenant_name,
      });

      // Redirect to tenant subdomain
      if (
        data.tenant_domain &&
        initiateTenantSessionTransfer({
          accessToken: data.access,
          refreshToken: data.refresh,
          tenantDomain: data.tenant_domain,
          tenantName: data.tenant_name,
          tenantSchema: data.tenant_schema,
          username: "jwt@example.com",
          source: "homepage_demo",
        })
      ) {
        return;
      }

      {
        toast.error("No tenant domain in response");
      }
    } catch (error: unknown) {
      const errorMsg =
        typeof error === "object" && error !== null && "response" in error
          ? (
              error as {
                response?: { data?: { error?: string; detail?: string } };
              }
            ).response?.data?.error ||
            (error as { response?: { data?: { detail?: string } } }).response
              ?.data?.detail
          : undefined;

      logAuthEvent("LOGIN_FAILED", {
        username: "jwt@example.com",
        error: errorMsg ?? "Unknown error",
        source: "homepage_demo_button",
      });

      toast.error(errorMsg ?? "Login failed");
    }
  };

  const ping = async () => {
    const { data } = await api.get("/ping/");
    toast.info(`ping: ${JSON.stringify(data)}`);
  };

  const pay = async () => {
    if (!STRIPE_PK) {
      toast.error("Missing VITE_STRIPE_PUBLIC_KEY");
      return;
    }
    const { data } = await api.post("/pay/create-checkout-session/", {
      amount: 500,
      currency: "usd",
      name: "Demo",
    });
    if (data?.url) {
      window.location.href = data.url;
    } else {
      toast.error("No checkout URL from backend");
    }
  };

  return (
    <div className="min-h-screen bg-neutral-900 text-neutral-100 p-6">
      <div className="max-w-2xl mx-auto space-y-4">
        <h1 className="text-3xl font-bold">StatusWatch (dev)</h1>

        <div className="flex gap-3">
          <button
            onClick={loginDemo}
            className="px-4 py-2 rounded-xl bg-neutral-800 hover:bg-neutral-700"
            title="uses /api/auth/token/"
          >
            Login (jwt@example.com/TestPass123!)
          </button>

          <button
            onClick={ping}
            className="px-4 py-2 rounded-xl bg-neutral-800 hover:bg-neutral-700"
          >
            Ping API
          </button>

          <button
            onClick={pay}
            className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500"
          >
            Pay $5
          </button>
        </div>

        <div>
          <Link
            to="/register"
            className="inline-flex items-center gap-2 rounded-xl bg-sky-500 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-400"
          >
            Create your organization
          </Link>
        </div>

        <div className="space-y-2">
          <p className="text-sm text-neutral-400">
            API base:{" "}
            <code>
              {import.meta.env.VITE_API_BASE || "window.location.origin/api"}
            </code>
          </p>
          <p className="text-xs text-neutral-500">
            💡 Demo: Click "Login" to authenticate as JWT user
            <br />
            You'll be redirected to: <code>acme.localhost:5173/dashboard</code>
            <br />
            Or create your own organization and get your own subdomain!
          </p>
        </div>
      </div>
    </div>
  );
}
