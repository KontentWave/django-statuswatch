import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";

import {
  cancelBillingSubscription,
  createBillingCheckoutSession,
  createBillingPortalSession,
} from "@/lib/billing-client";
import { fetchCurrentUser } from "@/lib/api";
import { logBillingEvent } from "@/lib/billing-logger";
import { redirectTo } from "@/lib/navigation";
import { clearCheckoutPlan, rememberCheckoutPlan } from "@/lib/billing-storage";
import { logSubscriptionEvent } from "@/lib/subscription-logger";
import { SubscriptionPlan, useSubscriptionStore } from "@/stores/subscription";

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
  const setSubscriptionPlan = useSubscriptionStore((state) => state.setPlan);

  const userQuery = useQuery({
    queryKey: ["current-user"],
    queryFn: fetchCurrentUser,
    retry: false,
    refetchOnMount: "always",
    refetchOnWindowFocus: "always",
    staleTime: 0,
  });
  const currentUser = userQuery.data;

  useEffect(() => {
    if (!currentUser?.plan) {
      return;
    }

    const nextPlan = currentUser.plan as SubscriptionPlan;
    if (nextPlan !== subscriptionPlan) {
      setSubscriptionPlan(nextPlan);
    }
  }, [currentUser?.plan, setSubscriptionPlan, subscriptionPlan]);

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

  const portalMutation = useMutation({
    mutationFn: () => createBillingPortalSession(),
    onMutate: () => {
      setErrorMessage(null);
      setIsRedirecting(false);
      void logBillingEvent({
        event: "portal",
        phase: "start",
        plan: subscriptionPlan,
        source: "billing-page",
      });
    },
    onSuccess: (redirectUrl) => {
      setIsRedirecting(true);
      void logBillingEvent({
        event: "portal",
        phase: "success",
        plan: subscriptionPlan,
        redirectUrl,
        source: "billing-page",
      });
      redirectTo(redirectUrl);
    },
    onError: (err: unknown) => {
      const message =
        err instanceof Error
          ? err.message
          : "We could not open the Stripe billing portal.";
      setErrorMessage(message);
      setIsRedirecting(false);
      void logBillingEvent({
        event: "portal",
        phase: "error",
        plan: subscriptionPlan,
        message,
        source: "billing-page",
      });
    },
  });

  const handleUpgradeClick = () => {
    rememberCheckoutPlan("pro");
    upgradeMutation.mutate();
  };

  const handleManageSubscription = () => {
    void logSubscriptionEvent({
      event: "plan_change",
      action: "cta_click",
      plan: subscriptionPlan,
      source: "billing-page",
    });
    portalMutation.mutate();
  };

  const cancelMutation = useMutation({
    mutationFn: cancelBillingSubscription,
    onMutate: () => {
      setErrorMessage(null);
      setIsRedirecting(false);
      void logBillingEvent({
        event: "cancellation",
        phase: "start",
        plan: subscriptionPlan,
        source: "billing-page",
      });
      void logSubscriptionEvent({
        event: "plan_change",
        action: "cancel_start",
        plan: subscriptionPlan,
        source: "billing-page",
      });
    },
    onSuccess: async (plan) => {
      const nextPlan = plan as SubscriptionPlan;
      setSubscriptionPlan(nextPlan);
      await logBillingEvent({
        event: "cancellation",
        phase: "success",
        plan: nextPlan,
        source: "billing-page",
      });
      await logSubscriptionEvent({
        event: "plan_change",
        action: "cancel_success",
        plan: nextPlan,
        source: "billing-page",
      });
      void userQuery.refetch();
    },
    onError: async (err: unknown) => {
      const message =
        err instanceof Error
          ? err.message
          : "We could not cancel your subscription. Please try again.";
      setErrorMessage(message);
      await logBillingEvent({
        event: "cancellation",
        phase: "error",
        plan: subscriptionPlan,
        message,
        source: "billing-page",
      });
      await logSubscriptionEvent({
        event: "plan_change",
        action: "cancel_error",
        plan: subscriptionPlan,
        source: "billing-page",
        error: message,
      });
    },
  });

  const handleNavigateBack = () => {
    void navigate({ to: "/dashboard" });
  };

  const showBusyState =
    upgradeMutation.isPending ||
    portalMutation.isPending ||
    cancelMutation.isPending ||
    isRedirecting;
  const disableUpgradeCta = showBusyState || !planState.canUpgrade;
  const disableManageCta =
    portalMutation.isPending || cancelMutation.isPending || isRedirecting;
  const disableCancelCta = cancelMutation.isPending || isRedirecting;
  const showManageButton = subscriptionPlan === "pro";
  const showCancelButton = subscriptionPlan === "pro";

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
        <div className="flex flex-wrap items-center gap-2">
          {showManageButton && (
            <button
              type="button"
              onClick={handleManageSubscription}
              disabled={disableManageCta}
              className="inline-flex items-center rounded-md border border-border bg-background px-4 py-2 text-sm font-medium text-foreground shadow-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-70"
            >
              {disableManageCta ? "Opening portal…" : "Manage Subscription"}
            </button>
          )}
          {showCancelButton && (
            <button
              type="button"
              onClick={() => cancelMutation.mutate()}
              disabled={disableCancelCta}
              className="inline-flex items-center rounded-md border border-destructive/40 bg-destructive/10 px-4 py-2 text-sm font-medium text-destructive shadow-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-destructive focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-70"
            >
              {disableCancelCta ? "Cancelling…" : "Cancel Plan"}
            </button>
          )}
          <button
            type="button"
            onClick={handleNavigateBack}
            className="inline-flex items-center rounded-md border border-border bg-background px-4 py-2 text-sm font-medium text-foreground shadow-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
          >
            Back to Dashboard
          </button>
        </div>
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
