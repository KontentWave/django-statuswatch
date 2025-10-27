import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import BillingPage from "@/pages/Billing";
import {
  resetSubscriptionStore,
  useSubscriptionStore,
} from "@/stores/subscription";

const {
  createBillingCheckoutSessionMock,
  createBillingPortalSessionMock,
  cancelBillingSubscriptionMock,
  fetchCurrentUserMock,
  logBillingEventMock,
  logSubscriptionEventMock,
  navigateMock,
  redirectToMock,
  rememberCheckoutPlanMock,
  clearCheckoutPlanMock,
} = vi.hoisted(() => ({
  createBillingCheckoutSessionMock: vi.fn(),
  createBillingPortalSessionMock: vi.fn(),
  cancelBillingSubscriptionMock: vi.fn(),
  fetchCurrentUserMock: vi.fn(),
  logBillingEventMock: vi.fn(),
  logSubscriptionEventMock: vi.fn(),
  navigateMock: vi.fn(),
  redirectToMock: vi.fn(),
  rememberCheckoutPlanMock: vi.fn(),
  clearCheckoutPlanMock: vi.fn(),
}));

vi.mock("@/lib/billing-client", () => ({
  createBillingCheckoutSession: () => createBillingCheckoutSessionMock(),
  createBillingPortalSession: () => createBillingPortalSessionMock(),
  cancelBillingSubscription: () => cancelBillingSubscriptionMock(),
}));

vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual<typeof import("@tanstack/react-router")>(
    "@tanstack/react-router"
  );
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

vi.mock("@/lib/api", () => ({
  fetchCurrentUser: () => fetchCurrentUserMock(),
}));

vi.mock("@/lib/billing-logger", () => ({
  logBillingEvent: (payload: unknown) => logBillingEventMock(payload),
}));

vi.mock("@/lib/subscription-logger", () => ({
  logSubscriptionEvent: (payload: unknown) => logSubscriptionEventMock(payload),
}));

vi.mock("@/lib/navigation", () => ({
  redirectTo: (url: string) => redirectToMock(url),
}));

vi.mock("@/lib/billing-storage", () => ({
  rememberCheckoutPlan: (plan: string) => rememberCheckoutPlanMock(plan),
  clearCheckoutPlan: () => clearCheckoutPlanMock(),
}));

function renderBillingPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <BillingPage />
    </QueryClientProvider>
  );
}

describe("BillingPage", () => {
  const defaultUser = {
    id: 1,
    username: "owner",
    email: "owner@example.com",
    first_name: "Owner",
    last_name: "User",
    is_staff: false,
    date_joined: new Date("2024-01-01T00:00:00Z").toISOString(),
    groups: [] as string[],
    plan: "free" as const,
  };

  beforeEach(() => {
    act(() => {
      resetSubscriptionStore();
    });
    createBillingCheckoutSessionMock.mockReset();
    createBillingPortalSessionMock.mockReset();
    cancelBillingSubscriptionMock.mockReset();
    fetchCurrentUserMock.mockReset();
    logBillingEventMock.mockReset();
    logSubscriptionEventMock.mockReset();
    navigateMock.mockReset();
    redirectToMock.mockReset();
    rememberCheckoutPlanMock.mockReset();
    clearCheckoutPlanMock.mockReset();
    fetchCurrentUserMock.mockResolvedValue({ ...defaultUser });
  });

  afterEach(() => {
    act(() => {
      resetSubscriptionStore();
    });
  });

  it("starts checkout flow and redirects when Stripe session succeeds", async () => {
    const redirectUrl = "https://stripe.test/sessions/abc123";
    createBillingCheckoutSessionMock.mockResolvedValue(redirectUrl);

    renderBillingPage();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /upgrade to pro/i }));

    await waitFor(() => {
      expect(createBillingCheckoutSessionMock).toHaveBeenCalledTimes(1);
    });

    expect(rememberCheckoutPlanMock).toHaveBeenCalledWith("pro");

    // First call: config event on component mount (useEffect)
    expect(logBillingEventMock).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({
        event: "config",
        phase: "completed",
        plan: "free",
      })
    );

    // Second call: checkout start when button clicked
    expect(logBillingEventMock).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        event: "checkout",
        phase: "start",
        plan: "pro",
      })
    );

    // Third call: checkout success after API response
    await waitFor(() => {
      expect(logBillingEventMock).toHaveBeenNthCalledWith(
        3,
        expect.objectContaining({
          event: "checkout",
          phase: "success",
          plan: "pro",
          redirectUrl,
        })
      );
    });

    expect(redirectToMock).toHaveBeenCalledWith(redirectUrl);
    expect(clearCheckoutPlanMock).not.toHaveBeenCalled();
  });

  it("surfaces a helpful error message when checkout fails", async () => {
    createBillingCheckoutSessionMock.mockRejectedValue(
      new Error("Stripe is temporarily unavailable")
    );

    renderBillingPage();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /upgrade to pro/i }));

    expect(
      await screen.findByText(/stripe is temporarily unavailable/i)
    ).toBeInTheDocument();

    expect(rememberCheckoutPlanMock).toHaveBeenCalledWith("pro");

    await waitFor(() => {
      expect(logBillingEventMock).toHaveBeenCalledWith(
        expect.objectContaining({
          event: "checkout",
          phase: "error",
          plan: "pro",
          message: "Stripe is temporarily unavailable",
        })
      );
    });

    expect(clearCheckoutPlanMock).toHaveBeenCalledTimes(1);
  });

  it("navigates back to the dashboard when requested", async () => {
    renderBillingPage();

    const user = userEvent.setup();
    await user.click(
      screen.getByRole("button", { name: /back to dashboard/i })
    );

    expect(navigateMock).toHaveBeenCalledWith({ to: "/dashboard" });
  });

  it("opens the Stripe billing portal for Pro users", async () => {
    const redirectUrl = "https://stripe.test/portal/bps_test_123";
    createBillingPortalSessionMock.mockResolvedValue(redirectUrl);
    fetchCurrentUserMock.mockResolvedValue({
      ...defaultUser,
      plan: "pro",
    });
    act(() => {
      useSubscriptionStore.getState().setPlan("pro");
    });

    renderBillingPage();

    const manageButton = screen.getByRole("button", {
      name: /manage subscription/i,
    });

    const user = userEvent.setup();
    await user.click(manageButton);

    await waitFor(() => {
      expect(createBillingPortalSessionMock).toHaveBeenCalledTimes(1);
    });

    expect(logSubscriptionEventMock).toHaveBeenCalledWith(
      expect.objectContaining({
        event: "plan_change",
        action: "cta_click",
        plan: "pro",
      })
    );

    const billingCalls = logBillingEventMock.mock.calls.filter((call) => {
      const payload = call[0] as { event?: string };
      return payload.event === "portal";
    });

    expect(billingCalls).toHaveLength(2);
    expect(billingCalls[0][0]).toMatchObject({
      event: "portal",
      phase: "start",
      plan: "pro",
    });
    expect(billingCalls[1][0]).toMatchObject({
      event: "portal",
      phase: "success",
      plan: "pro",
      redirectUrl,
    });

    expect(rememberCheckoutPlanMock).not.toHaveBeenCalled();
    expect(clearCheckoutPlanMock).not.toHaveBeenCalled();
    expect(redirectToMock).toHaveBeenCalledWith(redirectUrl);
  });

  it("shows an error when the billing portal is unavailable", async () => {
    createBillingPortalSessionMock.mockRejectedValue(
      new Error("Billing portal temporarily unavailable")
    );
    fetchCurrentUserMock.mockResolvedValue({
      ...defaultUser,
      plan: "pro",
    });
    act(() => {
      useSubscriptionStore.getState().setPlan("pro");
    });

    renderBillingPage();

    const manageButton = screen.getByRole("button", {
      name: /manage subscription/i,
    });

    const user = userEvent.setup();
    await user.click(manageButton);

    expect(
      await screen.findByText(/billing portal temporarily unavailable/i)
    ).toBeInTheDocument();

    const billingCalls = logBillingEventMock.mock.calls.filter((call) => {
      const payload = call[0] as { event?: string };
      return payload.event === "portal";
    });

    expect(billingCalls).toHaveLength(2);
    expect(billingCalls[1][0]).toMatchObject({
      event: "portal",
      phase: "error",
      plan: "pro",
      message: "Billing portal temporarily unavailable",
    });

    expect(redirectToMock).not.toHaveBeenCalled();
  });

  it("cancels the subscription and downgrades the plan", async () => {
    fetchCurrentUserMock
      .mockResolvedValueOnce({
        ...defaultUser,
        plan: "pro",
      })
      .mockResolvedValueOnce({
        ...defaultUser,
        plan: "free",
      });
    cancelBillingSubscriptionMock.mockResolvedValue("free");
    act(() => {
      useSubscriptionStore.getState().setPlan("pro");
    });

    renderBillingPage();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /cancel plan/i }));

    await waitFor(() => {
      expect(cancelBillingSubscriptionMock).toHaveBeenCalledTimes(1);
    });

    expect(useSubscriptionStore.getState().plan).toBe("free");

    const cancellationEvents = logBillingEventMock.mock.calls
      .map(
        (call) => call[0] as { event?: string; phase?: string; plan?: string }
      )
      .filter((payload) => payload.event === "cancellation");

    expect(cancellationEvents).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          event: "cancellation",
          phase: "start",
          plan: "pro",
        }),
        expect.objectContaining({
          event: "cancellation",
          phase: "success",
          plan: "free",
        }),
      ])
    );

    expect(logSubscriptionEventMock).toHaveBeenCalledWith(
      expect.objectContaining({
        event: "plan_change",
        action: "cancel_success",
        plan: "free",
      })
    );
  });

  it("surfaces an error when cancellation fails", async () => {
    fetchCurrentUserMock.mockResolvedValue({
      ...defaultUser,
      plan: "pro",
    });
    cancelBillingSubscriptionMock.mockRejectedValue(
      new Error("Unable to cancel subscription")
    );
    act(() => {
      useSubscriptionStore.getState().setPlan("pro");
    });

    renderBillingPage();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /cancel plan/i }));

    expect(
      await screen.findByText(/unable to cancel subscription/i)
    ).toBeInTheDocument();

    const cancellationErrors = logBillingEventMock.mock.calls
      .map(
        (call) =>
          call[0] as { event?: string; phase?: string; message?: string }
      )
      .filter(
        (payload) =>
          payload.event === "cancellation" && payload.phase === "error"
      );

    expect(cancellationErrors[0]).toMatchObject({
      message: "Unable to cancel subscription",
    });

    expect(logSubscriptionEventMock).toHaveBeenCalledWith(
      expect.objectContaining({
        event: "plan_change",
        action: "cancel_error",
        error: "Unable to cancel subscription",
      })
    );
  });
});
