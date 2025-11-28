import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";

import { logBillingEvent } from "@/lib/billing-logger";
import { consumeCheckoutPlan } from "@/lib/billing-storage";
import { fetchCurrentUser } from "@/lib/api";
import { logSubscriptionEvent } from "@/lib/subscription-logger";
import { useSubscriptionStore } from "@/stores/subscription";
import type { SubscriptionPlan } from "@/types/api";

function formatPlanLabel(plan: string): string {
  if (!plan || plan === "unknown") {
    return "your upgraded plan";
  }

  return `${plan.slice(0, 1).toUpperCase()}${plan.slice(1)}`;
}

const PLAN_REFRESH_MAX_ATTEMPTS = 6;
const PLAN_REFRESH_INTERVAL_MS = 5_000;

export default function BillingSuccessPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const setSubscriptionPlan = useSubscriptionStore((state) => state.setPlan);

  const searchParams = new URLSearchParams(location.search ?? "");
  const sessionId = searchParams.get("session_id") ?? undefined;

  const [selectedPlan] = useState<string>(
    () => consumeCheckoutPlan() ?? "unknown"
  );
  const normalizedPlan = useMemo<SubscriptionPlan | "unknown">(() => {
    if (
      selectedPlan === "free" ||
      selectedPlan === "pro" ||
      selectedPlan === "canceled"
    ) {
      return selectedPlan;
    }
    return "unknown";
  }, [selectedPlan]);

  useEffect(() => {
    const message = sessionId
      ? undefined
      : "Checkout return missing session_id parameter.";

    void logBillingEvent({
      event: "checkout",
      phase: "completed",
      plan: selectedPlan,
      sessionId,
      message,
      source: "billing-success-page",
      redirectScheduled: !sessionId,
      inferredPlan: normalizedPlan,
      outcome: sessionId ? "verified_session" : "missing_session",
    });
  }, [normalizedPlan, selectedPlan, sessionId]);

  useEffect(() => {
    if (normalizedPlan !== "unknown" && sessionId) {
      setSubscriptionPlan(normalizedPlan);
    }
  }, [normalizedPlan, sessionId, setSubscriptionPlan]);

  useEffect(() => {
    if (!sessionId) {
      if (typeof window === "undefined") {
        return undefined;
      }

      const timeout = window.setTimeout(() => {
        void navigate({ to: "/billing", replace: true });
      }, 4000);

      return () => window.clearTimeout(timeout);
    }
    if (typeof window === "undefined") {
      return undefined;
    }

    let cancelled = false;
    let timeoutId: ReturnType<typeof globalThis.setTimeout> | null = null;
    let attempt = 0;
    let invalidated = false;
    let lastKnownPlan: SubscriptionPlan | "unknown" | undefined =
      normalizedPlan;

    const runAttempt = async (reason: "initial" | "retry") => {
      attempt += 1;

      await logSubscriptionEvent({
        event: "plan_change",
        action: "refresh_start",
        attempt,
        reason,
        sessionId,
        selectedPlan,
        inferredPlan: normalizedPlan,
      });

      try {
        if (!invalidated) {
          invalidated = true;
          await queryClient.invalidateQueries({
            queryKey: ["current-user"],
          });
        }

        const user = await queryClient.fetchQuery({
          queryKey: ["current-user"],
          queryFn: fetchCurrentUser,
          staleTime: 0,
        });

        if (cancelled) {
          return;
        }

        lastKnownPlan = user.plan;

        await logSubscriptionEvent({
          event: "plan_change",
          action: "refresh_success",
          attempt,
          sessionId,
          refreshedPlan: user.plan,
        });

        setSubscriptionPlan(user.plan);

        if (user.plan !== "free") {
          return;
        }
      } catch (error) {
        const errorDetails =
          error instanceof Error
            ? { errorName: error.name, errorMessage: error.message }
            : { errorMessage: String(error) };

        await logSubscriptionEvent({
          event: "plan_change",
          action: "refresh_error",
          attempt,
          sessionId,
          ...errorDetails,
        });
      }

      if (cancelled) {
        return;
      }

      if (attempt >= PLAN_REFRESH_MAX_ATTEMPTS) {
        await logSubscriptionEvent({
          event: "plan_change",
          action: "refresh_error",
          attempt,
          sessionId,
          reason: "max_attempts_reached",
          lastKnownPlan,
        });
        return;
      }

      timeoutId = globalThis.setTimeout(() => {
        void runAttempt("retry");
      }, PLAN_REFRESH_INTERVAL_MS);
    };

    void runAttempt("initial");

    return () => {
      cancelled = true;
      if (timeoutId !== null) {
        globalThis.clearTimeout(timeoutId);
        timeoutId = null;
      }
    };
  }, [
    navigate,
    normalizedPlan,
    queryClient,
    selectedPlan,
    sessionId,
    setSubscriptionPlan,
  ]);

  const planLabel = formatPlanLabel(selectedPlan);

  const handleGoToDashboard = () => {
    void navigate({ to: "/dashboard" });
  };

  const handleManageBilling = () => {
    void navigate({ to: "/billing" });
  };

  return (
    <div className="mx-auto max-w-xl space-y-6 p-6">
      <header className="space-y-2 text-center">
        <h1 className="text-2xl font-semibold text-foreground">
          Checkout Complete
        </h1>
        <p className="text-sm text-muted-foreground">
          Thanks for upgrading to {planLabel}. We will email you a confirmation
          shortly. You can return to your dashboard while we finalize the
          subscription.
        </p>
      </header>

      <section className="rounded-md border border-border bg-card p-4 text-sm text-muted-foreground">
        {sessionId ? (
          <div className="space-y-2">
            <p>Your Stripe session finished successfully.</p>
            <p>
              <span className="font-medium text-foreground">Session ID:</span>{" "}
              <code className="break-all text-xs text-foreground">
                {sessionId}
              </code>
            </p>
            <p className="text-xs">
              Keep this reference handy if you need help from support.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            <p>We could not verify a recent checkout session.</p>
            <p>
              Start a new upgrade from the billing page to unlock Pro features.
              You will be redirected automatically in a moment.
            </p>
          </div>
        )}
      </section>

      <div className="flex flex-wrap justify-center gap-3">
        <button
          type="button"
          onClick={handleGoToDashboard}
          className="inline-flex items-center rounded-md border border-border bg-background px-4 py-2 text-sm font-medium text-foreground shadow-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
        >
          Go to Dashboard
        </button>
        <button
          type="button"
          onClick={handleManageBilling}
          className="inline-flex items-center rounded-md border border-transparent bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
        >
          Manage Billing
        </button>
      </div>
    </div>
  );
}
