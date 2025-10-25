import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import BillingPage from "@/pages/Billing";

const {
  createBillingCheckoutSessionMock,
  logBillingEventMock,
  navigateMock,
  redirectToMock,
  rememberCheckoutPlanMock,
  clearCheckoutPlanMock,
} = vi.hoisted(() => ({
  createBillingCheckoutSessionMock: vi.fn(),
  logBillingEventMock: vi.fn(),
  navigateMock: vi.fn(),
  redirectToMock: vi.fn(),
  rememberCheckoutPlanMock: vi.fn(),
  clearCheckoutPlanMock: vi.fn(),
}));

vi.mock("@/lib/billing-client", () => ({
  createBillingCheckoutSession: () => createBillingCheckoutSessionMock(),
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

vi.mock("@/lib/billing-logger", () => ({
  logBillingEvent: (payload: unknown) => logBillingEventMock(payload),
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
  beforeEach(() => {
    createBillingCheckoutSessionMock.mockReset();
    logBillingEventMock.mockReset();
    navigateMock.mockReset();
    redirectToMock.mockReset();
    rememberCheckoutPlanMock.mockReset();
    clearCheckoutPlanMock.mockReset();
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

    expect(logBillingEventMock).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({
        event: "checkout",
        phase: "start",
        plan: "pro",
      })
    );

    await waitFor(() => {
      expect(logBillingEventMock).toHaveBeenNthCalledWith(
        2,
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
});
