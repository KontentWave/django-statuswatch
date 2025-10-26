import { useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";

import { createBillingCheckoutSession } from "@/lib/billing-client";
import { logBillingEvent } from "@/lib/billing-logger";
import { redirectTo } from "@/lib/navigation";
import { clearCheckoutPlan, rememberCheckoutPlan } from "@/lib/billing-storage";
import { logSubscriptionEvent } from "@/lib/subscription-logger";
import { useSubscriptionStore } from "@/stores/subscription";

const proPlanFeatures = [
  "Unlimited monitored endpoints",
  "15-second check intervals",
  "Email alerts for incidents",
  "Priority support",
];

const freePlanFeatures = [
  "Monitor up to 3 endpoints",
  "5-minute check intervals",
  "Email summaries",
];

export default function BillingPage() {
  const navigate = useNavigate();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isRedirecting, setIsRedirecting] = useState(false);
  const subscriptionPlan = useSubscriptionStore((state) => state.plan);

  const planState = useMemo(() => {
    switch (subscriptionPlan) {
      case "pro":
        return {
          statusLabel: "Pro plan active",
          freeCardMessage:
            "Your workspace has already upgraded from this plan.",
          proButtonLabel: "Current Plan",
          canUpgrade: false,
        } as const;
      case "canceled":
        return {
          statusLabel: "Subscription canceled",
          freeCardMessage: "You are currently viewing the fallback free tier.",
          proButtonLabel: "Re-activate Pro",
          canUpgrade: true,
        } as const;
      default:
        return {
          statusLabel: "Free plan active",
          freeCardMessage: "You are currently on this plan.",
          proButtonLabel: "Upgrade to Pro",
          canUpgrade: true,
        } as const;
    }
  }, [subscriptionPlan]);

  const upgradeMutation = useMutation({
    mutationFn: () => createBillingCheckoutSession("pro"),
    onMutate: () => {
      setErrorMessage(null);
      setIsRedirecting(false);
      void logBillingEvent({
        event: "checkout",
        phase: "start",
        plan: "pro",
      });
    },
    onSuccess: (redirectUrl) => {
      setIsRedirecting(true);
      void logBillingEvent({
        event: "checkout",
        phase: "success",
        plan: "pro",
        redirectUrl,
      });
      redirectTo(redirectUrl);
    },
    onError: (err: unknown) => {
      const message =
        err instanceof Error
          ? err.message
          : "We could not start the Stripe checkout session.";
      setErrorMessage(message);
      setIsRedirecting(false);
      void logBillingEvent({
        event: "checkout",
        phase: "error",
        plan: "pro",
        message,
      });
      clearCheckoutPlan();
    },
  });

  const handleUpgradeClick = () => {
    rememberCheckoutPlan("pro");
    upgradeMutation.mutate();
  };

  const handleNavigateBack = () => {
    void navigate({ to: "/dashboard" });
  };

  const showBusyState = upgradeMutation.isPending || isRedirecting;
  const disableUpgradeCta = showBusyState || !planState.canUpgrade;

  useEffect(() => {
    void logBillingEvent({
      event: "config",
      phase: "completed",
      plan: subscriptionPlan,
      source: "billing-page",
      message: "Detected current subscription state",
    });
    void logSubscriptionEvent({
      event: "plan_change",
      action: "state_detected",
      plan: subscriptionPlan,
      source: "billing-page",
    });
  }, [subscriptionPlan]);

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold">Billing &amp; Plans</h1>
          <p className="text-sm text-muted-foreground">
            Choose the plan that fits your organization. Upgrade to unlock
            advanced monitoring and priority support.
          </p>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {planState.statusLabel}
          </p>
        </div>
        <button
          type="button"
          onClick={handleNavigateBack}
          className="inline-flex items-center rounded-md border border-border bg-background px-4 py-2 text-sm font-medium text-foreground shadow-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
        >
          Back to Dashboard
        </button>
      </header>

      <section className="grid gap-4 sm:grid-cols-2">
        <article className="flex flex-col justify-between rounded-lg border border-border bg-card p-5 shadow-sm">
          <div className="space-y-3">
            <h2 className="text-xl font-semibold">Free</h2>
            <p className="text-sm text-muted-foreground">
              Perfect to get started monitoring a few critical services.
            </p>
            <p className="text-2xl font-bold text-foreground">$0</p>
            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
              {freePlanFeatures.map((feature) => (
                <li key={feature}>• {feature}</li>
              ))}
            </ul>
          </div>
          <p className="mt-4 text-sm text-muted-foreground">
            {planState.freeCardMessage}
          </p>
        </article>

        <article className="flex flex-col justify-between rounded-lg border border-primary bg-card p-5 shadow-md">
          <div className="space-y-3">
            <h2 className="flex items-center justify-between text-xl font-semibold">
              Pro
              <span className="text-base font-medium text-primary">$29/mo</span>
            </h2>
            <p className="text-sm text-muted-foreground">
              Scale monitoring with unlimited endpoints and faster checks.
            </p>
            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
              {proPlanFeatures.map((feature) => (
                <li key={feature}>• {feature}</li>
              ))}
            </ul>
          </div>
          <button
            type="button"
            onClick={handleUpgradeClick}
            disabled={disableUpgradeCta}
            className="mt-4 inline-flex items-center justify-center rounded-md border border-transparent bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-70"
          >
            {showBusyState ? "Redirecting…" : planState.proButtonLabel}
          </button>
        </article>
      </section>

      {errorMessage && (
        <section className="rounded border border-red-200 bg-red-50 p-4">
          <p className="text-sm text-red-600">{errorMessage}</p>
        </section>
      )}

      <section className="rounded border border-border bg-card p-4 text-sm text-muted-foreground">
        <h3 className="text-sm font-semibold text-foreground">
          What happens next?
        </h3>
        <ol className="mt-2 list-decimal space-y-1 pl-4">
          <li>We open a secure Stripe checkout session in a new page.</li>
          <li>Complete payment using your preferred method.</li>
          <li>You are redirected back to StatusWatch with confirmation.</li>
        </ol>
        <p className="mt-3">
          Need help? Reach out to{" "}
          <a className="underline" href="mailto:support@statuswatch.local">
            support@statuswatch.local
          </a>
          .
        </p>
      </section>
    </div>
  );
}
