import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import BillingCancelPage from "@/pages/BillingCancel";

const LOG_FILE_PATH = `${process.cwd()}/logs/billing-events.log`;

const {
  logBillingEventMock,
  navigateMock,
  consumeCheckoutPlanMock,
  locationSearchRef,
  persistBillingLog,
} = vi.hoisted(() => {
  const persistBillingLog = async (payload: unknown) => {
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    await fs.mkdir(path.dirname(LOG_FILE_PATH), { recursive: true });
    await fs.appendFile(
      LOG_FILE_PATH,
      `${JSON.stringify({ test: "billing-cancel", payload })}\n`,
      { encoding: "utf8" }
    );
    return undefined;
  };

  return {
    logBillingEventMock: vi.fn(persistBillingLog),
    navigateMock: vi.fn(),
    consumeCheckoutPlanMock: vi.fn(),
    locationSearchRef: {
      current: "?session_id=cs_cancel&reason=user_canceled",
    },
    persistBillingLog,
  };
});

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

function mockImmediateTimeouts() {
  const callbacks: Array<(() => void) | null> = [];
  const schedule =
    typeof queueMicrotask === "function"
      ? queueMicrotask
      : (callback: () => void) => {
          void Promise.resolve().then(callback);
        };

  const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout").mockImplementation(((
    handler: TimerHandler,
    timeout?: number,
    ...args: unknown[]
  ) => {
    void timeout;
    const index =
      callbacks.push(() => {
        if (typeof handler === "function") {
          (handler as (...cbArgs: unknown[]) => void)(...args);
        }
      }) - 1;
    schedule(() => {
      const callback = callbacks[index];
      if (callback) {
        callbacks[index] = null;
        callback();
      }
    });
    return (index + 1) as unknown as ReturnType<typeof globalThis.setTimeout>;
  }) as unknown as typeof globalThis.setTimeout);

  const clearTimeoutSpy = vi
    .spyOn(globalThis, "clearTimeout")
    .mockImplementation(((
      identifier: ReturnType<typeof globalThis.setTimeout>
    ) => {
      const index = Number(identifier) - 1;
      if (index >= 0 && index < callbacks.length) {
        callbacks[index] = null;
      }
    }) as unknown as typeof globalThis.clearTimeout);

  return { setTimeoutSpy, clearTimeoutSpy };
}

describe("BillingCancelPage", () => {
  beforeEach(() => {
    logBillingEventMock.mockImplementation(persistBillingLog);
    logBillingEventMock.mockClear();
    navigateMock.mockReset();
    consumeCheckoutPlanMock.mockReset();
    consumeCheckoutPlanMock.mockReturnValue("pro");
    locationSearchRef.current = "?session_id=cs_cancel&reason=user_canceled";
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
          cancellationReason: "user_canceled",
          source: "billing-cancel-page",
        })
      );
    });

    expect(
      screen.getByRole("heading", { name: /checkout canceled/i })
    ).toBeInTheDocument();
    expect(
      screen.getByText(/stripe reported: user_canceled/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/reference session id/i)).toBeInTheDocument();
  });

  it("handles missing parameters by redirecting", async () => {
    const { setTimeoutSpy, clearTimeoutSpy } = mockImmediateTimeouts();
    locationSearchRef.current = "";
    consumeCheckoutPlanMock.mockReturnValue("unknown");

    render(<BillingCancelPage />);

    await waitFor(() => {
      expect(logBillingEventMock).toHaveBeenCalledWith(
        expect.objectContaining({
          redirectScheduled: true,
          sessionId: undefined,
          message: expect.stringMatching(/canceled the stripe checkout flow/i),
        })
      );
    });

    expect(
      screen.getByText(/could not find a recent checkout/i)
    ).toBeInTheDocument();
    expect(navigateMock).toHaveBeenCalledWith({
      to: "/billing",
      replace: true,
    });

    setTimeoutSpy.mockRestore();
    clearTimeoutSpy.mockRestore();
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
