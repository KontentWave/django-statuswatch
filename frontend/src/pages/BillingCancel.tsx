import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "@tanstack/react-router";

import { logBillingEvent } from "@/lib/billing-logger";
import { consumeCheckoutPlan } from "@/lib/billing-storage";

function formatPlanLabel(plan: string): string {
  if (!plan || plan === "unknown") {
    return "your upgrade";
  }

  return `${plan.slice(0, 1).toUpperCase()}${plan.slice(1)}`;
}

export default function BillingCancelPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const searchParams = new URLSearchParams(location.search ?? "");
  const sessionId = searchParams.get("session_id") ?? undefined;
  const cancellationReason = searchParams.get("reason") ?? undefined;

  const [selectedPlan] = useState<string>(
    () => consumeCheckoutPlan() ?? "unknown"
  );

  useEffect(() => {
    const message =
      cancellationReason ?? "User canceled the Stripe checkout flow.";

    void logBillingEvent({
      event: "checkout",
      phase: "canceled",
      plan: selectedPlan,
      sessionId,
      message,
      source: "billing-cancel-page",
      redirectScheduled: !sessionId,
      cancellationReason,
    });
  }, [selectedPlan, sessionId, cancellationReason]);

  useEffect(() => {
    if (sessionId) {
      return;
    }

    if (typeof window === "undefined") {
      return undefined;
    }

    const timeout = window.setTimeout(() => {
      void navigate({ to: "/billing", replace: true });
    }, 4000);

    return () => window.clearTimeout(timeout);
  }, [navigate, sessionId]);

  const planLabel = formatPlanLabel(selectedPlan);

  const handleTryAgain = () => {
    void navigate({ to: "/billing" });
  };

  const handleGoToDashboard = () => {
    void navigate({ to: "/dashboard" });
  };

  return (
    <div className="mx-auto max-w-xl space-y-6 p-6">
      <header className="space-y-2 text-center">
        <h1 className="text-2xl font-semibold text-foreground">
          Checkout Canceled
        </h1>
        <p className="text-sm text-muted-foreground">
          We did not complete {planLabel}. You can restart the upgrade at any
          time from the billing page.
        </p>
      </header>

      <section className="rounded-md border border-border bg-card p-4 text-sm text-muted-foreground">
        <p>
          {cancellationReason
            ? `Stripe reported: ${cancellationReason}`
            : "We could not find a recent checkout to cancel. You will be redirected back to billing shortly."}
        </p>
        {sessionId ? (
          <p className="mt-2 text-xs">
            Reference session ID:{" "}
            <code className="break-all text-foreground">{sessionId}</code>
          </p>
        ) : null}
      </section>

      <div className="flex flex-wrap justify-center gap-3">
        <button
          type="button"
          onClick={handleTryAgain}
          className="inline-flex items-center rounded-md border border-transparent bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
        >
          Try Again
        </button>
        <button
          type="button"
          onClick={handleGoToDashboard}
          className="inline-flex items-center rounded-md border border-border bg-background px-4 py-2 text-sm font-medium text-foreground shadow-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
        >
          Go to Dashboard
        </button>
      </div>
    </div>
  );
}
