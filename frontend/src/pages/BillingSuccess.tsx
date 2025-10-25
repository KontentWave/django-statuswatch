import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "@tanstack/react-router";

import { logBillingEvent } from "@/lib/billing-logger";
import { consumeCheckoutPlan } from "@/lib/billing-storage";

function formatPlanLabel(plan: string): string {
  if (!plan || plan === "unknown") {
    return "your upgraded plan";
  }

  return `${plan.slice(0, 1).toUpperCase()}${plan.slice(1)}`;
}

export default function BillingSuccessPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const searchParams = new URLSearchParams(location.search ?? "");
  const sessionId = searchParams.get("session_id") ?? undefined;

  const [selectedPlan] = useState<string>(
    () => consumeCheckoutPlan() ?? "unknown"
  );

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
    });
  }, [selectedPlan, sessionId]);

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
            <p>Your checkout completed, but we could not read a session ID.</p>
            <p>
              If you need assistance, reach out to{" "}
              <a className="underline" href="mailto:support@statuswatch.local">
                support@statuswatch.local
              </a>
              .
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
