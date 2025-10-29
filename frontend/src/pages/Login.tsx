import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import type { AxiosError } from "axios";
import { useLocation, useNavigate } from "@tanstack/react-router";

import { api } from "@/lib/api";
import { customZodResolver } from "@/lib/zodResolver";
import { storeAuthTokens } from "@/lib/auth";
import { logAuthEvent } from "@/lib/auth-logger";

const loginSchema = z.object({
  email: z
    .string()
    .min(1, "Email is required.")
    .email("Enter a valid email address."),
  password: z.string().min(1, "Password is required."),
});

type LoginFormValues = z.infer<typeof loginSchema>;

type TenantOption = {
  tenant_schema: string;
  tenant_name: string;
  tenant_id: number;
};

type LoginApiResponse = {
  access?: string;
  refresh?: string;
  detail?: string;
  // Multi-tenant response fields
  tenant_schema?: string;
  tenant_name?: string;
  tenant_domain?: string;
  user?: {
    id: number;
    username: string;
    email: string;
    first_name?: string;
    last_name?: string;
  };
  // Multiple tenants response
  multiple_tenants?: boolean;
  tenants?: TenantOption[];
  message?: string;
  // Error field
  error?: string;
};

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [formError, setFormError] = useState<string | null>(null);

  // Tenant selection state
  const [showTenantSelector, setShowTenantSelector] = useState(false);
  const [availableTenants, setAvailableTenants] = useState<TenantOption[]>([]);
  const [selectedTenant, setSelectedTenant] = useState<string | null>(null);
  const [loginCredentials, setLoginCredentials] = useState<{
    email: string;
    password: string;
  } | null>(null);

  const registrationMessage = useMemo(() => {
    const state = location.state;
    if (state && typeof state === "object" && "message" in state) {
      const message = (state as { message?: unknown }).message;
      return typeof message === "string" ? message : null;
    }
    return null;
  }, [location.state]);

  const redirectTo = useMemo<"/dashboard" | null>(() => {
    const state = location.state;
    if (state && typeof state === "object" && "redirectTo" in state) {
      const destination = (state as { redirectTo?: unknown }).redirectTo;
      return destination === "/dashboard" ? "/dashboard" : null;
    }
    return null;
  }, [location.state]);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: customZodResolver(loginSchema),
    mode: "onSubmit",
    defaultValues: {
      email: "",
      password: "",
    },
  });

  const onSubmit = async (values: LoginFormValues) => {
    setFormError(null);
    logAuthEvent("LOGIN_ATTEMPT", {
      username: values.email,
      source: "login_page",
    });

    try {
      // Use new multi-tenant login endpoint
      const { data } = await api.post<LoginApiResponse>("/auth/login/", {
        username: values.email,
        password: values.password,
        tenant_schema: selectedTenant, // Include selected tenant if present
      });

      // Check if multiple tenants found
      if (data?.multiple_tenants && data?.tenants && data.tenants.length > 0) {
        logAuthEvent("MULTIPLE_TENANTS_FOUND", {
          username: values.email,
          tenant_count: data.tenants.length,
          tenants: data.tenants.map((t) => t.tenant_name).join(", "),
        });

        // Store credentials for re-submission after tenant selection
        setLoginCredentials({ email: values.email, password: values.password });
        setAvailableTenants(data.tenants);
        setShowTenantSelector(true);
        return; // Stop here, wait for tenant selection
      }

      // Normal login flow - single tenant or tenant selected
      const accessToken = data?.access;
      if (!accessToken) {
        throw new Error("Missing access token in response.");
      }

      storeAuthTokens({ access: accessToken, refresh: data?.refresh });
      logAuthEvent("TOKEN_STORED", {
        username: values.email,
        hasAccess: true,
        hasRefresh: !!data?.refresh,
        tenant_schema: data?.tenant_schema,
        tenant_name: data?.tenant_name,
      });
      logAuthEvent("LOGIN_SUCCESS", {
        username: values.email,
        tenant: data?.tenant_name,
      });

      // Redirect to tenant subdomain
      if (data?.tenant_domain) {
        const port = window.location.port || "5173";
        const protocol = window.location.protocol;

        // Extract hostname without port (in case backend returns domain with port)
        const hostname = data.tenant_domain.split(":")[0];
        const tenantUrl = `${protocol}//${hostname}:${port}/dashboard`;

        logAuthEvent("NAVIGATION_TO_DASHBOARD", {
          from: "login_page",
          username: values.email,
          destination: tenantUrl,
          tenant: data.tenant_name,
        });

        console.log(`[LOGIN] Redirecting to tenant subdomain: ${tenantUrl}`);
        window.location.href = tenantUrl;
      } else {
        // Fallback: navigate within same origin
        const destination = (redirectTo ?? "/dashboard") as "/dashboard";
        logAuthEvent("NAVIGATION_TO_DASHBOARD", {
          from: "login_page",
          username: values.email,
          destination,
        });
        await navigate({ to: destination, replace: true });
      }
    } catch (err) {
      const error = err as AxiosError<LoginApiResponse>;
      const errorMessage =
        error.response?.data?.error ??
        error.response?.data?.detail ??
        (error instanceof Error ? error.message : null);

      logAuthEvent("LOGIN_FAILED", {
        username: values.email,
        error: errorMessage ?? "Unknown error",
        source: "login_page",
      });
      setFormError(errorMessage ?? "Invalid email or password.");
    }
  };

  return (
    <div className="mx-auto max-w-md space-y-6 p-6">
      <header className="space-y-2 text-center">
        <h1 className="text-2xl font-semibold">Sign in to StatusWatch</h1>
        <p className="text-sm text-muted-foreground">
          Enter your workspace email to access your dashboard.
        </p>
        {registrationMessage && (
          <div className="rounded border border-emerald-200 bg-emerald-50 p-3 text-left">
            <p className="text-sm text-emerald-700">{registrationMessage}</p>
          </div>
        )}
      </header>

      <form className="space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
        <div className="space-y-1">
          <label className="block text-sm font-medium" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            className={`w-full rounded border px-3 py-2 ${
              errors.email
                ? "border-red-500 focus:border-red-500 focus:ring-red-500"
                : "border-border"
            }`}
            {...register("email")}
          />
          {errors.email && (
            <p className="text-sm text-red-600">{errors.email.message}</p>
          )}
        </div>

        <div className="space-y-1">
          <label className="block text-sm font-medium" htmlFor="password">
            Password
          </label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            className={`w-full rounded border px-3 py-2 ${
              errors.password
                ? "border-red-500 focus:border-red-500 focus:ring-red-500"
                : "border-border"
            }`}
            {...register("password")}
          />
          {errors.password && (
            <p className="text-sm text-red-600">{errors.password.message}</p>
          )}
        </div>

        {formError && (
          <div className="rounded border border-red-200 bg-red-50 p-3">
            <p className="text-sm text-red-600">{formError}</p>
          </div>
        )}

        <button
          type="submit"
          className="w-full rounded bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50"
          disabled={isSubmitting}
        >
          {isSubmitting ? "Signing In…" : "Sign In"}
        </button>
      </form>

      {/* Tenant Selector - shown when multiple tenants found */}
      {showTenantSelector && availableTenants.length > 0 && (
        <div className="mt-6 space-y-4 rounded border border-border bg-card p-4">
          <div className="space-y-2">
            <p className="text-sm font-medium">Multiple Organizations Found</p>
            <p className="text-sm text-muted-foreground">
              Your email exists in multiple organizations. Please select which
              one you want to access:
            </p>
          </div>

          <div className="space-y-1">
            <label
              className="block text-sm font-medium"
              htmlFor="tenant-select"
            >
              Organization
            </label>
            <select
              id="tenant-select"
              value={selectedTenant || ""}
              onChange={(e) => setSelectedTenant(e.target.value)}
              className="w-full rounded border border-border bg-background px-3 py-2"
            >
              <option value="">-- Select an organization --</option>
              {availableTenants.map((tenant) => (
                <option key={tenant.tenant_schema} value={tenant.tenant_schema}>
                  {tenant.tenant_name}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={async () => {
              if (!selectedTenant || !loginCredentials) return;

              setFormError(null);
              logAuthEvent("TENANT_SELECTED", {
                email: loginCredentials.email,
                selected_tenant: selectedTenant,
                selected_tenant_name: availableTenants.find(
                  (t) => t.tenant_schema === selectedTenant
                )?.tenant_name,
              });

              try {
                // Re-submit login with selected tenant
                const { data } = await api.post<LoginApiResponse>(
                  "/auth/login/",
                  {
                    username: loginCredentials.email,
                    password: loginCredentials.password,
                    tenant_schema: selectedTenant,
                  }
                );

                const accessToken = data?.access;
                if (!accessToken) {
                  throw new Error("Missing access token in response.");
                }

                storeAuthTokens({
                  access: accessToken,
                  refresh: data?.refresh,
                });
                logAuthEvent("TOKEN_STORED", {
                  username: loginCredentials.email,
                  hasAccess: true,
                  hasRefresh: !!data?.refresh,
                  tenant_schema: data?.tenant_schema,
                  tenant_name: data?.tenant_name,
                });
                logAuthEvent("LOGIN_SUCCESS", {
                  username: loginCredentials.email,
                  tenant: data?.tenant_name,
                });

                // Redirect to tenant subdomain
                if (data?.tenant_domain) {
                  const port = window.location.port || "5173";
                  const protocol = window.location.protocol;
                  const hostname = data.tenant_domain.split(":")[0];
                  const tenantUrl = `${protocol}//${hostname}:${port}/dashboard`;

                  logAuthEvent("NAVIGATION_TO_DASHBOARD", {
                    from: "tenant_selector",
                    username: loginCredentials.email,
                    destination: tenantUrl,
                    tenant: data.tenant_name,
                  });

                  console.log(
                    `[LOGIN] Redirecting to tenant subdomain: ${tenantUrl}`
                  );
                  window.location.href = tenantUrl;
                }
              } catch (err) {
                const error = err as AxiosError<LoginApiResponse>;
                const errorMessage =
                  error.response?.data?.error ??
                  error.response?.data?.detail ??
                  (error instanceof Error ? error.message : null);

                logAuthEvent("TENANT_LOGIN_FAILED", {
                  email: loginCredentials.email,
                  selected_tenant: selectedTenant,
                  error: errorMessage ?? "Unknown error",
                });
                setFormError(
                  errorMessage ?? "Login failed for selected organization."
                );
              }
            }}
            disabled={!selectedTenant}
            className="w-full rounded bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50"
          >
            {selectedTenant
              ? `Continue to ${
                  availableTenants.find(
                    (t) => t.tenant_schema === selectedTenant
                  )?.tenant_name
                }`
              : "Select an organization to continue"}
          </button>

          <button
            onClick={() => {
              logAuthEvent("TENANT_SELECTOR_CANCELLED", {
                email: loginCredentials?.email,
              });
              setShowTenantSelector(false);
              setAvailableTenants([]);
              setSelectedTenant(null);
              setLoginCredentials(null);
              setFormError(null);
            }}
            className="w-full rounded border border-border bg-background px-3 py-2 text-sm font-medium text-foreground hover:bg-muted"
          >
            Use Different Email
          </button>
        </div>
      )}
    </div>
  );
}
