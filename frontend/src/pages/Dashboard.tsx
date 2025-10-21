import { useEffect, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { AxiosError } from "axios";

import { fetchCurrentUser, submitLogout } from "@/lib/api";
import { clearAuthTokens, getRefreshToken } from "@/lib/auth";

export default function DashboardPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [logoutError, setLogoutError] = useState<string | null>(null);
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["current-user"],
    queryFn: fetchCurrentUser,
    retry: false,
  });

  const logoutMutation = useMutation({
    mutationFn: async () => {
      const refreshToken = getRefreshToken();
      if (refreshToken) {
        await submitLogout(refreshToken);
      }
    },
    onSuccess: () => {
      clearAuthTokens();
      queryClient.clear();
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

  const handleLogout = () => {
    setLogoutError(null);
    logoutMutation.mutate();
  };

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold">Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            Welcome back! Your workspace data will appear here soon.
          </p>
        </div>
        <button
          type="button"
          onClick={handleLogout}
          disabled={logoutMutation.isPending}
          className="inline-flex items-center rounded-md border border-transparent bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-70"
        >
          {logoutMutation.isPending ? "Logging out…" : "Log Out"}
        </button>
      </header>

      {isLoading && (
        <section className="rounded border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">Loading your profile…</p>
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
    </div>
  );
}
