import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { AxiosError } from "axios";

import AppHeader from "@/components/AppHeader";
import EndpointTable from "@/components/EndpointTable";
import { fetchCurrentUser, submitLogout } from "@/lib/api";
import { clearAuthTokens, getRefreshToken } from "@/lib/auth";
import {
  createEndpoint,
  deleteEndpoint,
  listEndpoints,
  type CreateEndpointRequest,
  type EndpointListResponse,
} from "@/lib/endpoint-client";
import { logDashboardEvent } from "@/lib/dashboard-logger";
import { logSubscriptionEvent } from "@/lib/subscription-logger";
import { logAuthEvent } from "@/lib/auth-logger";
import { useSubscriptionStore } from "@/stores/subscription";

const ENDPOINTS_QUERY_KEY = "endpoints";
const FREE_PLAN_ENDPOINT_LIMIT = 3;

export default function DashboardPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [logoutError, setLogoutError] = useState<string | null>(null);
  const [endpointForm, setEndpointForm] = useState({
    name: "",
    url: "",
    interval_minutes: 5,
  });
  const [endpointFormError, setEndpointFormError] = useState<string | null>(
    null
  );
  const [page, setPage] = useState(1);
  const pageSizeRef = useRef(0);
  const gatingLoggedRef = useRef(false);
  const subscriptionPlan = useSubscriptionStore((state) => state.plan);
  const setSubscriptionPlan = useSubscriptionStore((state) => state.setPlan);
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["current-user"],
    queryFn: fetchCurrentUser,
    retry: false,
    refetchOnMount: "always",
    refetchOnWindowFocus: "always",
    staleTime: 0,
  });
  const endpointsQuery = useQuery<EndpointListResponse, Error>({
    queryKey: [ENDPOINTS_QUERY_KEY, page],
    queryFn: () => listEndpoints({ page }),
    retry: false,
    placeholderData: (previousData) => previousData,
    refetchInterval: 15_000,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: "always",
    refetchOnReconnect: true,
    staleTime: 0,
  });

  useEffect(() => {
    if (!data?.plan) {
      return;
    }

    setSubscriptionPlan(data.plan);
    void logSubscriptionEvent({
      event: "gating",
      action: "hydrate",
      plan: data.plan,
    });
  }, [data?.plan, setSubscriptionPlan]);

  const activePlan = data?.plan ?? subscriptionPlan;
  const totalCount = endpointsQuery.data?.count ?? 0;
  const hasReachedFreeLimit =
    activePlan === "free" && totalCount >= FREE_PLAN_ENDPOINT_LIMIT;

  const logoutMutation = useMutation({
    mutationFn: async () => {
      logAuthEvent("LOGOUT", { username: data?.email, source: "dashboard" });
      const refreshToken = getRefreshToken();
      if (refreshToken) {
        await submitLogout(refreshToken);
      }
    },
    onSuccess: () => {
      clearAuthTokens();
      logAuthEvent("TOKEN_CLEARED", { source: "logout_success" });
      queryClient.clear();
      logAuthEvent("NAVIGATION_TO_LOGIN", {
        from: "dashboard",
        reason: "logout",
      });
      void navigate({
        to: "/login",
        replace: true,
        state: (prev) => ({
          ...(typeof prev === "object" && prev !== null ? prev : {}),
          message: "You have been logged out.",
        }),
      });
    },
    onError: (logoutErr: unknown) => {
      const axiosError = logoutErr as AxiosError<{
        detail?: string;
        error?: string;
      }>;
      const fallback =
        axiosError.message || "We could not log you out. Please try again.";
      setLogoutError(
        axiosError.response?.data?.detail ||
          axiosError.response?.data?.error ||
          fallback
      );
    },
  });

  const createEndpointMutation = useMutation({
    mutationFn: (payload: CreateEndpointRequest) => createEndpoint(payload),
    onMutate: () => {
      setEndpointFormError(null);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [ENDPOINTS_QUERY_KEY] });
      setEndpointForm({ name: "", url: "", interval_minutes: 5 });
    },
    onError: (createErr: unknown) => {
      const axiosError = createErr as AxiosError<{
        detail?: string;
        error?: string;
      }>;
      const fallback = axiosError.message || "We could not save the endpoint.";
      setEndpointFormError(
        axiosError.response?.data?.detail ||
          axiosError.response?.data?.error ||
          fallback
      );
    },
  });

  const deleteEndpointMutation = useMutation({
    mutationFn: (endpointId: string) => deleteEndpoint(endpointId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [ENDPOINTS_QUERY_KEY] });
    },
  });

  useEffect(() => {
    if (!isError) return;

    const axiosError = error as AxiosError | undefined;
    if (axiosError?.response?.status !== 401) return;

    clearAuthTokens();
    void navigate({
      to: "/login",
      replace: true,
      state: (prev) => ({
        ...(typeof prev === "object" && prev !== null ? prev : {}),
        message: "Your session expired. Please sign in again.",
      }),
    });
  }, [error, isError, navigate]);

  useEffect(() => {
    if (!endpointsQuery.isSuccess) {
      return;
    }
    if (
      page > 1 &&
      endpointsQuery.data &&
      endpointsQuery.data.results.length === 0
    ) {
      setPage((prev) => Math.max(1, prev - 1));
    }
  }, [endpointsQuery.data, endpointsQuery.isSuccess, page]);

  const handleLogout = () => {
    setLogoutError(null);
    logoutMutation.mutate();
  };

  const navigateToBilling = (source: "header" | "gating") => {
    void logSubscriptionEvent({
      event: "gating",
      action: "cta_click",
      plan: activePlan,
      source,
    });
    void navigate({ to: "/billing" });
  };

  const handleEndpointInputChange = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const { name, value } = event.target;
    setEndpointForm((prev) => ({
      ...prev,
      [name]: name === "interval_minutes" ? Number(value) : value,
    }));
  };

  const handleCreateEndpoint = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!endpointForm.url.trim()) {
      setEndpointFormError("Endpoint URL is required.");
      return;
    }
    if (hasReachedFreeLimit) {
      setEndpointFormError(
        "You have reached the Free plan limit. Upgrade to Pro to add more endpoints."
      );
      void logSubscriptionEvent({
        event: "gating",
        action: "cta_click",
        plan: activePlan,
        source: "form_blocked",
        totalCount,
        limit: FREE_PLAN_ENDPOINT_LIMIT,
      });
      return;
    }
    setEndpointFormError(null);
    createEndpointMutation.mutate({
      name: endpointForm.name.trim() || undefined,
      url: endpointForm.url.trim(),
      interval_minutes: endpointForm.interval_minutes,
    });
  };

  const handleDeleteEndpoint = (endpointId: string) => {
    deleteEndpointMutation.mutate(endpointId);
  };

  const endpointRows = useMemo(() => {
    if (!endpointsQuery.data) {
      return [];
    }
    return endpointsQuery.data.results;
  }, [endpointsQuery.data]);

  if (endpointRows.length > 0 && endpointRows.length > pageSizeRef.current) {
    pageSizeRef.current = endpointRows.length;
  }

  useEffect(() => {
    if (hasReachedFreeLimit && !gatingLoggedRef.current) {
      gatingLoggedRef.current = true;
      void logSubscriptionEvent({
        event: "gating",
        action: "limit_reached",
        plan: activePlan,
        totalCount,
        limit: FREE_PLAN_ENDPOINT_LIMIT,
      });
    }

    if (!hasReachedFreeLimit) {
      gatingLoggedRef.current = false;
    }
  }, [hasReachedFreeLimit, activePlan, totalCount]);

  const totalPages = useMemo(() => {
    if (!endpointsQuery.data) {
      return 1;
    }
    const trackedSize = pageSizeRef.current || endpointRows.length || 1;
    const pageSize = Math.max(1, trackedSize);
    return Math.max(1, Math.ceil(endpointsQuery.data.count / pageSize));
  }, [endpointRows.length, endpointsQuery.data]);

  const hasNextPage = Boolean(endpointsQuery.data?.next) || page < totalPages;
  const hasPreviousPage = page > 1;
  const endpointsErrorMessage = endpointsQuery.isError
    ? endpointsQuery.error?.message ?? "Unable to load endpoints."
    : null;

  const deletePendingId = deleteEndpointMutation.variables as
    | string
    | undefined;

  const handleChangePage = (nextPage: number) => {
    if (nextPage < 1 || nextPage > totalPages || nextPage === page) {
      return;
    }
    setPage(nextPage);
    void logDashboardEvent({
      event: "pagination",
      phase: "start",
      page: nextPage,
      fromPage: page,
      direction: nextPage > page ? "forward" : "backward",
      totalPages,
    });
  };

  return (
    <div className="mx-auto max-w-3xl space-y-4 pb-6">
      <AppHeader
        onManageBilling={() => navigateToBilling("header")}
        onLogout={handleLogout}
        logoutPending={logoutMutation.isPending}
      />
      <main className="space-y-4 px-6">
        <section className="flex flex-col gap-2 text-sm text-muted-foreground">
          <h1 className="text-2xl font-semibold text-foreground">Dashboard</h1>
          <p>Welcome back! Your workspace data will appear here soon.</p>
        </section>

        {isLoading && (
          <section className="rounded border border-border bg-card p-4">
            <p className="text-sm text-muted-foreground">
              Loading your profile…
            </p>
          </section>
        )}

        {logoutError && (
          <section className="rounded border border-red-200 bg-red-50 p-4">
            <p className="text-sm text-red-600">{logoutError}</p>
          </section>
        )}

        {!isLoading && data && (
          <section className="space-y-3 rounded border border-border bg-card p-4">
            <div>
              <h2 className="text-lg font-semibold">Account</h2>
              <p className="text-sm text-muted-foreground">
                You are signed in as{" "}
                <span className="font-medium">{data.email}</span>.
              </p>
            </div>
            <dl className="grid gap-3 text-sm text-muted-foreground sm:grid-cols-2">
              <div>
                <dt className="font-semibold text-foreground">Username</dt>
                <dd>{data.username}</dd>
              </div>
              <div>
                <dt className="font-semibold text-foreground">Joined</dt>
                <dd>{new Date(data.date_joined).toLocaleString()}</dd>
              </div>
              <div>
                <dt className="font-semibold text-foreground">Groups</dt>
                <dd>{data.groups.length ? data.groups.join(", ") : "None"}</dd>
              </div>
              <div>
                <dt className="font-semibold text-foreground">Staff</dt>
                <dd>{data.is_staff ? "Yes" : "No"}</dd>
              </div>
              <div>
                <dt className="font-semibold text-foreground">Plan</dt>
                <dd className="capitalize">{activePlan}</dd>
              </div>
            </dl>
          </section>
        )}

        {isError && !isLoading && (
          <section className="rounded border border-red-200 bg-red-50 p-4">
            <p className="text-sm text-red-600">
              {(error as Error)?.message ?? "Unable to load your account."}
            </p>
          </section>
        )}

        <section className="space-y-4 rounded border border-border bg-card p-4">
          <div className="space-y-2">
            <h2 className="text-lg font-semibold">Monitored Endpoints</h2>
            <p className="text-sm text-muted-foreground">
              Track health checks for URLs in your organization.
            </p>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  void endpointsQuery.refetch();
                }}
                disabled={endpointsQuery.isFetching}
                className="inline-flex items-center rounded-md border border-border bg-background px-3 py-1.5 text-xs font-medium text-foreground transition focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {endpointsQuery.isFetching ? "Refreshing…" : "Refresh"}
              </button>
              <span className="text-xs text-muted-foreground">
                Updated{" "}
                {endpointsQuery.dataUpdatedAt
                  ? new Date(endpointsQuery.dataUpdatedAt).toLocaleTimeString()
                  : "just now"}
              </span>
            </div>
          </div>

          <EndpointTable
            rows={endpointRows}
            page={page}
            totalPages={totalPages}
            totalCount={totalCount}
            isLoading={endpointsQuery.isLoading}
            isFetching={endpointsQuery.isFetching}
            isError={endpointsQuery.isError}
            isSuccess={endpointsQuery.isSuccess}
            errorMessage={endpointsErrorMessage}
            hasNextPage={hasNextPage}
            hasPreviousPage={hasPreviousPage}
            onPageChange={handleChangePage}
            onDelete={handleDeleteEndpoint}
            pendingDeleteId={deletePendingId}
            isDeletePending={deleteEndpointMutation.isPending}
          />

          <form className="space-y-3" onSubmit={handleCreateEndpoint}>
            <h3 className="text-sm font-semibold text-foreground">
              Add Endpoint
            </h3>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="space-y-1 text-sm">
                <span className="font-medium text-foreground">
                  Name (optional)
                </span>
                <input
                  type="text"
                  name="name"
                  value={endpointForm.name}
                  onChange={handleEndpointInputChange}
                  placeholder="Billing API"
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={hasReachedFreeLimit}
                />
              </label>
              <label className="space-y-1 text-sm sm:col-span-2">
                <span className="font-medium text-foreground">URL</span>
                <input
                  type="url"
                  name="url"
                  required
                  value={endpointForm.url}
                  onChange={handleEndpointInputChange}
                  placeholder="https://example.com/health"
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={hasReachedFreeLimit}
                />
              </label>
              <label className="space-y-1 text-sm">
                <span className="font-medium text-foreground">
                  Interval (minutes)
                </span>
                <input
                  type="number"
                  min={1}
                  max={24 * 60}
                  step={1}
                  name="interval_minutes"
                  value={endpointForm.interval_minutes}
                  onChange={handleEndpointInputChange}
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={hasReachedFreeLimit}
                />
              </label>
            </div>

            {endpointFormError && (
              <p className="text-sm text-red-600">{endpointFormError}</p>
            )}

            {createEndpointMutation.isError && !endpointFormError && (
              <p className="text-sm text-red-600">
                We could not save the endpoint.
              </p>
            )}

            {hasReachedFreeLimit ? (
              <div className="flex flex-col items-start justify-between gap-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 sm:flex-row sm:items-center">
                <p>
                  You have reached the Free plan limit of{" "}
                  {FREE_PLAN_ENDPOINT_LIMIT} endpoints. Upgrade to unlock
                  unlimited monitoring.
                </p>
                <button
                  type="button"
                  onClick={() => navigateToBilling("gating")}
                  className="inline-flex items-center rounded-md border border-transparent bg-amber-500 px-4 py-2 text-sm font-semibold text-white shadow transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-2"
                >
                  Upgrade to Pro
                </button>
              </div>
            ) : (
              <div className="flex items-center justify-end gap-2">
                <button
                  type="submit"
                  disabled={createEndpointMutation.isPending}
                  className="inline-flex items-center rounded-md border border-transparent bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {createEndpointMutation.isPending
                    ? "Adding…"
                    : "Add Endpoint"}
                </button>
              </div>
            )}
          </form>
        </section>
      </main>
    </div>
  );
}
