import { Link } from "@tanstack/react-router";

import { useSubscriptionStore } from "@/stores/subscription";

interface AppHeaderProps {
  onManageBilling?: () => void;
  onLogout?: () => void;
  logoutPending?: boolean;
}

export default function AppHeader({
  onManageBilling,
  onLogout,
  logoutPending = false,
}: AppHeaderProps) {
  const plan = useSubscriptionStore((state) => state.plan);

  return (
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-background/80 px-6 py-4 backdrop-blur">
      <div className="flex items-center gap-3">
        <Link to="/dashboard" className="text-lg font-semibold text-foreground">
          StatusWatch
        </Link>
        <span className="inline-flex items-center rounded-full border border-border bg-muted px-3 py-0.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {plan === "pro"
            ? "Pro Plan"
            : plan === "canceled"
            ? "Canceled"
            : "Free Plan"}
        </span>
      </div>
      <div className="flex items-center gap-2">
        {onManageBilling ? (
          <button
            type="button"
            onClick={onManageBilling}
            className="inline-flex items-center rounded-md border border-border bg-background px-4 py-2 text-sm font-medium text-foreground shadow-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
          >
            Manage Billing
          </button>
        ) : null}
        {onLogout ? (
          <button
            type="button"
            onClick={onLogout}
            disabled={logoutPending}
            className="inline-flex items-center rounded-md border border-transparent bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-70"
          >
            {logoutPending ? "Logging out…" : "Log Out"}
          </button>
        ) : null}
      </div>
    </header>
  );
}
