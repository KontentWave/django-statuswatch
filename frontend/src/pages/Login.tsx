import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import type { AxiosError } from "axios";
import { useLocation, useNavigate } from "@tanstack/react-router";

import { api } from "@/lib/api";
import { customZodResolver } from "@/lib/zodResolver";
import { storeAuthTokens } from "@/lib/auth";
import { logAuthEvent } from "@/lib/auth-logger";
import { initiateTenantSessionTransfer } from "@/lib/tenant-session";
import type { AllowedRedirectPath } from "@/lib/redirects";
import { DEFAULT_REDIRECT, sanitizeRedirectPath } from "@/lib/redirects";
const RESEND_GENERIC_MESSAGE =
  "If an account exists for this email, we've sent a fresh verification link.";

const RESEND_ERROR_FALLBACK =
  "We couldn't resend the verification email. Please try again.";

type LoginErrorPayload =
  | string
  | {
      message?: string;
      code?: string;
    };

const extractMessage = (value: unknown): string | null => {
  if (typeof value === "string") {
    return value;
  }

  if (
    value &&
    typeof value === "object" &&
    "message" in value &&
    typeof (value as { message?: unknown }).message === "string"
  ) {
    return (value as { message: string }).message;
  }

  return null;
};

const resolveMessage = (value: unknown, fallback: string): string => {
  return extractMessage(value) ?? fallback;
};

const extractErrorCode = (value: unknown): string | null => {
  if (
    value &&
    typeof value === "object" &&
    "code" in value &&
    typeof (value as { code?: unknown }).code === "string"
  ) {
    return (value as { code: string }).code;
  }

  return null;
};

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
  error?: LoginErrorPayload;
};

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [formError, setFormError] = useState<string | null>(null);
  const [isApplyingTransfer, setIsApplyingTransfer] = useState(false);
  const [pendingVerificationEmail, setPendingVerificationEmail] = useState<
    string | null
  >(null);
  const [resendStatus, setResendStatus] = useState<string | null>(null);
  const [isResending, setIsResending] = useState(false);
  const transferHandledRef = useRef(false);

  // Tenant selection state
  const [showTenantSelector, setShowTenantSelector] = useState(false);
  const [availableTenants, setAvailableTenants] = useState<TenantOption[]>([]);
  const [selectedTenant, setSelectedTenant] = useState<string | null>(null);
  const [loginCredentials, setLoginCredentials] = useState<{
    email: string;
    password: string;
  } | null>(null);

  useEffect(() => {
    if (transferHandledRef.current || typeof window === "undefined") {
      return;
    }

    const hash = window.location.hash;
    if (!hash || !hash.includes("session=")) {
      return;
    }

    const normalizedHash = hash.startsWith("#") ? hash.slice(1) : hash;
    const params = new URLSearchParams(normalizedHash);
    const encodedPayload = params.get("session");
    if (!encodedPayload) {
      return;
    }

    transferHandledRef.current = true;
    setIsApplyingTransfer(true);

    try {
      const decoded = JSON.parse(atob(encodedPayload)) as {
        access?: string;
        refresh?: string | null;
        tenant_schema?: string | null;
        tenant_name?: string | null;
        username?: string | null;
        source?: string | null;
      };

      if (!decoded?.access) {
        throw new Error("Transfer payload missing access token.");
      }

      storeAuthTokens({
        access: decoded.access,
        refresh: decoded.refresh ?? null,
      });

      logAuthEvent("TENANT_TRANSFER_APPLIED", {
        tenant_schema: decoded.tenant_schema,
        tenant_name: decoded.tenant_name,
        hasRefresh: !!decoded.refresh,
        source: params.get("source") ?? decoded.source ?? "unknown",
      });
      const rawSearch = window.location.search ?? "";
      const normalizedSearch = rawSearch
        ? rawSearch.startsWith("?")
          ? rawSearch
          : `?${rawSearch}`
        : "";
      const redirectParams = new URLSearchParams(normalizedSearch);
      const redirectCandidate = sanitizeRedirectPath(
        redirectParams.get("redirect") ?? redirectParams.get("next"),
      );
      const destination = redirectCandidate ?? DEFAULT_REDIRECT;

      window.history.replaceState(null, "", window.location.pathname);
      void navigate({ to: destination, replace: true });
    } catch (error) {
      logAuthEvent("TENANT_TRANSFER_FAILED", {
        source: params.get("source") ?? "unknown",
        error: error instanceof Error ? error.message : String(error),
      });
      window.history.replaceState(null, "", window.location.pathname);
      setFormError(
        "We couldn't finalize your sign-in automatically. Please sign in again.",
      );
    } finally {
      setIsApplyingTransfer(false);
    }
  }, [navigate]);

  const registrationMessage = useMemo(() => {
    const state = location.state;
    if (state && typeof state === "object" && "message" in state) {
      const message = (state as { message?: unknown }).message;
      return typeof message === "string" ? message : null;
    }
    return null;
  }, [location.state]);

  const redirectFromState = useMemo<AllowedRedirectPath | null>(() => {
    const state = location.state;
    if (state && typeof state === "object" && "redirectTo" in state) {
      const destination = (state as { redirectTo?: unknown }).redirectTo;
      return sanitizeRedirectPath(destination);
    }
    return null;
  }, [location.state]);

  const redirectFromQuery = useMemo<AllowedRedirectPath | null>(() => {
    const search = location.searchStr ?? location.search ?? "";
    const normalized = search.startsWith("?") ? search : `?${search}`;
    const params = new URLSearchParams(normalized);
    const destination = params.get("redirect") ?? params.get("next");
    return sanitizeRedirectPath(destination);
  }, [location.search, location.searchStr]);

  const redirectTo = redirectFromState ?? redirectFromQuery;

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: customZodResolver(loginSchema),
    mode: "onSubmit",
    defaultValues: {
      email: "",
      password: "",
    },
  });

  const currentEmailValue = watch("email");

  useEffect(() => {
    setPendingVerificationEmail(null);
    setResendStatus(null);
  }, [currentEmailValue]);

  const emailUnverifiedMessage =
    "Email not verified. Please check your inbox for the verification link before signing in.";

  const onSubmit = async (values: LoginFormValues) => {
    setFormError(null);
    setPendingVerificationEmail(null);
    setResendStatus(null);
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

      let transferInitiated = false;
      if (data?.tenant_domain) {
        transferInitiated = initiateTenantSessionTransfer({
          accessToken,
          refreshToken: data?.refresh,
          tenantDomain: data.tenant_domain,
          tenantName: data?.tenant_name,
          tenantSchema: data?.tenant_schema,
          username: values.email,
          source: "login_page",
          redirectPath: redirectTo ?? null,
        });
      }

      if (transferInitiated) {
        setIsApplyingTransfer(true);
        return;
      }

      setIsApplyingTransfer(false);

      // Fallback: navigate within same origin
      const destination = redirectTo ?? DEFAULT_REDIRECT;
      logAuthEvent("NAVIGATION_TO_DASHBOARD", {
        from: "login_page",
        username: values.email,
        destination,
      });
      await navigate({ to: destination, replace: true });
    } catch (err) {
      const error = err as AxiosError<LoginApiResponse>;

      // Extract error message - handle both string and object formats
      const errorData = error.response?.data?.error;
      let errorMessage = extractMessage(errorData);
      const errorCode = extractErrorCode(errorData);

      // Fallback to detail or generic message
      if (!errorMessage) {
        errorMessage =
          error.response?.data?.detail ??
          (error instanceof Error ? error.message : null) ??
          "Invalid email or password.";
      }

      logAuthEvent("LOGIN_FAILED", {
        username: values.email,
        error: errorMessage,
        source: "login_page",
      });
      setIsApplyingTransfer(false);
      if (errorCode === "email_unverified") {
        setPendingVerificationEmail(values.email);
        setFormError(emailUnverifiedMessage);
        return;
      }

      setFormError(errorMessage);
    }
  };

  const handleResendVerification = useCallback(async () => {
    if (!pendingVerificationEmail) {
      return;
    }

    setIsResending(true);
    setResendStatus(null);

    try {
      const { data } = await api.post<{ detail?: unknown; error?: unknown }>(
        "/auth/resend-verification/",
        { email: pendingVerificationEmail },
      );

      const detail = resolveMessage(data?.detail, RESEND_GENERIC_MESSAGE);
      setResendStatus(detail);
    } catch (error) {
      const axiosError = error as AxiosError<{
        detail?: unknown;
        error?: unknown;
      }>;
      const detail = resolveMessage(
        axiosError.response?.data?.detail ?? axiosError.response?.data?.error,
        RESEND_ERROR_FALLBACK,
      );
      setResendStatus(detail);
    } finally {
      setIsResending(false);
    }
  }, [pendingVerificationEmail]);

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
          <div
            className={`rounded border p-3 ${
              pendingVerificationEmail
                ? "border-amber-300 bg-amber-50"
                : "border-red-200 bg-red-50"
            }`}
          >
            <p
              className={`text-sm ${
                pendingVerificationEmail ? "text-amber-900" : "text-red-600"
              }`}
            >
              {formError}
            </p>
            {pendingVerificationEmail && (
              <div className="mt-3 space-y-2">
                <button
                  type="button"
                  onClick={handleResendVerification}
                  disabled={isResending}
                  className="w-full rounded border border-amber-400 px-3 py-2 text-sm font-semibold text-amber-900 hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isResending ? "Resending…" : "Resend Verification Email"}
                </button>
                {resendStatus && (
                  <p className="text-sm text-amber-900">{resendStatus}</p>
                )}
              </div>
            )}
          </div>
        )}

        <button
          type="submit"
          className="w-full rounded bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50"
          disabled={isSubmitting || isApplyingTransfer}
          aria-disabled={isSubmitting || isApplyingTransfer}
        >
          {isSubmitting || isApplyingTransfer ? "Signing In…" : "Sign In"}
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
                  (t) => t.tenant_schema === selectedTenant,
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
                  },
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

                let transferStarted = false;
                if (data?.tenant_domain) {
                  transferStarted = initiateTenantSessionTransfer({
                    accessToken,
                    refreshToken: data?.refresh,
                    tenantDomain: data.tenant_domain,
                    tenantName: data?.tenant_name,
                    tenantSchema: data?.tenant_schema,
                    username: loginCredentials.email,
                    source: "tenant_selector",
                    redirectPath: redirectTo ?? null,
                  });
                }

                if (transferStarted) {
                  setIsApplyingTransfer(true);
                  return;
                }

                setIsApplyingTransfer(false);
              } catch (err) {
                const error = err as AxiosError<LoginApiResponse>;

                // Extract error message - handle both string and object formats
                const errorData = error.response?.data?.error;
                let errorMessage = extractMessage(errorData);
                const errorCode = extractErrorCode(errorData);

                // Fallback to detail or generic message
                if (!errorMessage) {
                  errorMessage =
                    error.response?.data?.detail ??
                    (error instanceof Error ? error.message : null) ??
                    "Login failed for selected organization.";
                }

                logAuthEvent("TENANT_LOGIN_FAILED", {
                  email: loginCredentials.email,
                  selected_tenant: selectedTenant,
                  error: errorMessage,
                });
                setIsApplyingTransfer(false);
                if (errorCode === "email_unverified") {
                  setPendingVerificationEmail(loginCredentials.email);
                  setFormError(emailUnverifiedMessage);
                } else {
                  setFormError(errorMessage);
                }
              }
            }}
            disabled={!selectedTenant || isApplyingTransfer}
            className="w-full rounded bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50"
          >
            {selectedTenant
              ? `Continue to ${
                  availableTenants.find(
                    (t) => t.tenant_schema === selectedTenant,
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
