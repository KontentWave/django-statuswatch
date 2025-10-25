import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import BillingSuccessPage from "@/pages/BillingSuccess";

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
  locationSearchRef: { current: "?session_id=cs_test_123" },
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
        pathname: "/billing/success",
        search: locationSearchRef.current,
        hash: "",
        key: "test",
        params: {},
        href: `/billing/success${locationSearchRef.current}`,
        searchStr: locationSearchRef.current,
        publicHref: `/billing/success${locationSearchRef.current}`,
        url: new URL(
          `http://localhost/billing/success${locationSearchRef.current}`
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

describe("BillingSuccessPage", () => {
  beforeEach(() => {
    logBillingEventMock.mockReset();
    logBillingEventMock.mockResolvedValue(undefined);
    navigateMock.mockReset();
    consumeCheckoutPlanMock.mockReset();
    consumeCheckoutPlanMock.mockReturnValue("pro");
    locationSearchRef.current = "?session_id=cs_test_123";
  });

  it("logs completion details and shows session information", async () => {
    render(<BillingSuccessPage />);

    await waitFor(() => {
      expect(logBillingEventMock).toHaveBeenCalledWith(
        expect.objectContaining({
          event: "checkout",
          phase: "completed",
          plan: "pro",
          sessionId: "cs_test_123",
          source: "billing-success-page",
        })
      );
    });

    expect(consumeCheckoutPlanMock).toHaveBeenCalledTimes(1);
    expect(
      screen.getByRole("heading", { name: /checkout complete/i })
    ).toBeInTheDocument();
    expect(screen.getByText(/session id/i)).toBeInTheDocument();
  });

  it("notes missing session id and logs message", async () => {
    locationSearchRef.current = "";

    render(<BillingSuccessPage />);

    await waitFor(() => {
      expect(logBillingEventMock).toHaveBeenCalledWith(
        expect.objectContaining({
          phase: "completed",
          message: expect.stringMatching(/missing session_id/i),
        })
      );
    });

    expect(
      screen.getByText(/could not read a session id/i)
    ).toBeInTheDocument();
  });

  it("navigates when actions are clicked", async () => {
    render(<BillingSuccessPage />);

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /go to dashboard/i }));
    await user.click(screen.getByRole("button", { name: /manage billing/i }));

    expect(navigateMock).toHaveBeenNthCalledWith(1, { to: "/dashboard" });
    expect(navigateMock).toHaveBeenNthCalledWith(2, { to: "/billing" });
  });
});
