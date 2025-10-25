import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import BillingCancelPage from "@/pages/BillingCancel";

const {
  logBillingEventMock,
  navigateMock,
  consumeCheckoutPlanMock,
  locationSearchRef,
} = vi.hoisted(() => ({
  logBillingEventMock: vi.fn(async (...args: unknown[]) => {
    void args;
    return undefined;
  }),
  navigateMock: vi.fn(),
  consumeCheckoutPlanMock: vi.fn(),
  locationSearchRef: { current: "?reason=user_canceled&session_id=cs_cancel" },
}));

vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual<typeof import("@tanstack/react-router")>(
    "@tanstack/react-router"
  );
  return {
    ...actual,
    useNavigate: () => navigateMock,
    useLocation: () =>
      ({
        pathname: "/billing/cancel",
        search: locationSearchRef.current,
        hash: "",
        key: "test",
        params: {},
        href: `/billing/cancel${locationSearchRef.current}`,
        searchStr: locationSearchRef.current,
        publicHref: `/billing/cancel${locationSearchRef.current}`,
        url: new URL(
          `http://localhost/billing/cancel${locationSearchRef.current}`
        ),
        state: undefined,
      } as unknown as ReturnType<typeof actual.useLocation>),
  };
});

vi.mock("@/lib/billing-logger", () => ({
  logBillingEvent: (payload: unknown) => logBillingEventMock(payload),
}));

vi.mock("@/lib/billing-storage", () => ({
  consumeCheckoutPlan: () => consumeCheckoutPlanMock(),
}));

describe("BillingCancelPage", () => {
  beforeEach(() => {
    logBillingEventMock.mockReset();
    logBillingEventMock.mockResolvedValue(undefined);
    navigateMock.mockReset();
    consumeCheckoutPlanMock.mockReset();
    consumeCheckoutPlanMock.mockReturnValue("pro");
    locationSearchRef.current = "?reason=user_canceled&session_id=cs_cancel";
  });

  it("logs cancellation details with context", async () => {
    render(<BillingCancelPage />);

    await waitFor(() => {
      expect(logBillingEventMock).toHaveBeenCalledWith(
        expect.objectContaining({
          event: "checkout",
          phase: "canceled",
          plan: "pro",
          sessionId: "cs_cancel",
          message: expect.stringMatching(/user_canceled/i),
          source: "billing-cancel-page",
        })
      );
    });

    expect(
      screen.getByRole("heading", { name: /checkout canceled/i })
    ).toBeInTheDocument();
    expect(screen.getByText(/user_canceled/i)).toBeInTheDocument();
  });

  it("handles missing parameters", async () => {
    locationSearchRef.current = "";
    consumeCheckoutPlanMock.mockReturnValue("unknown");

    render(<BillingCancelPage />);

    await waitFor(() => {
      expect(logBillingEventMock).toHaveBeenCalledWith(
        expect.objectContaining({
          message: expect.stringMatching(/canceled the stripe checkout flow/i),
        })
      );
    });

    expect(screen.getByText(/no additional information/i)).toBeInTheDocument();
  });

  it("provides navigation actions", async () => {
    render(<BillingCancelPage />);

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /try again/i }));
    await user.click(screen.getByRole("button", { name: /go to dashboard/i }));

    expect(navigateMock).toHaveBeenNthCalledWith(1, { to: "/billing" });
    expect(navigateMock).toHaveBeenNthCalledWith(2, { to: "/dashboard" });
  });
});
