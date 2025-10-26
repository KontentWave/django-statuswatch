import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import BillingSuccessPage from "@/pages/BillingSuccess";

const BILLING_LOG_FILE_PATH = `${process.cwd()}/logs/billing-events.log`;
const SUBSCRIPTION_LOG_FILE_PATH = `${process.cwd()}/logs/subscription-events.log`;

const {
  logBillingEventMock,
  logSubscriptionEventMock,
  navigateMock,
  consumeCheckoutPlanMock,
  locationSearchRef,
  invalidateQueriesMock,
  fetchQueryMock,
  setPlanMock,
  fetchCurrentUserMock,
  persistBillingLog,
  persistSubscriptionLog,
} = vi.hoisted(() => {
  const persistBillingLog = async (payload: unknown) => {
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    await fs.mkdir(path.dirname(BILLING_LOG_FILE_PATH), { recursive: true });
    await fs.appendFile(
      BILLING_LOG_FILE_PATH,
      `${JSON.stringify({ test: "billing-success", payload })}\n`,
      { encoding: "utf8" }
    );
    return undefined;
  };

  const persistSubscriptionLog = async (payload: unknown) => {
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    await fs.mkdir(path.dirname(SUBSCRIPTION_LOG_FILE_PATH), {
      recursive: true,
    });
    await fs.appendFile(
      SUBSCRIPTION_LOG_FILE_PATH,
      `${JSON.stringify({ test: "billing-success", payload })}\n`,
      { encoding: "utf8" }
    );
    return undefined;
  };

  return {
    logBillingEventMock: vi.fn(persistBillingLog),
    logSubscriptionEventMock: vi.fn(persistSubscriptionLog),
    navigateMock: vi.fn(),
    consumeCheckoutPlanMock: vi.fn(),
    locationSearchRef: { current: "?session_id=cs_test_123" },
    invalidateQueriesMock: vi.fn(),
    fetchQueryMock: vi.fn(),
    setPlanMock: vi.fn(),
    fetchCurrentUserMock: vi.fn(),
    persistBillingLog,
    persistSubscriptionLog,
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

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({
    invalidateQueries: invalidateQueriesMock,
    fetchQuery: fetchQueryMock,
  }),
}));

vi.mock("@/lib/billing-logger", () => ({
  logBillingEvent: (payload: unknown) => logBillingEventMock(payload),
}));

vi.mock("@/lib/subscription-logger", () => ({
  logSubscriptionEvent: (payload: unknown) => logSubscriptionEventMock(payload),
}));

vi.mock("@/lib/billing-storage", () => ({
  consumeCheckoutPlan: () => consumeCheckoutPlanMock(),
}));

vi.mock("@/stores/subscription", () => ({
  useSubscriptionStore: (
    selector: (state: {
      plan: string;
      setPlan: (plan: string) => void;
    }) => unknown
  ) => selector({ plan: "free", setPlan: setPlanMock }),
}));

vi.mock("@/lib/api", () => ({
  fetchCurrentUser: () => fetchCurrentUserMock(),
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

describe("BillingSuccessPage", () => {
  beforeEach(() => {
    logBillingEventMock.mockImplementation(persistBillingLog);
    logBillingEventMock.mockClear();
    logSubscriptionEventMock.mockImplementation(persistSubscriptionLog);
    logSubscriptionEventMock.mockClear();
    navigateMock.mockReset();
    consumeCheckoutPlanMock.mockReset();
    consumeCheckoutPlanMock.mockReturnValue("pro");
    locationSearchRef.current = "?session_id=cs_test_123";
    invalidateQueriesMock.mockReset();
    fetchQueryMock.mockReset();
    setPlanMock.mockReset();
    fetchCurrentUserMock.mockReset();
    fetchCurrentUserMock.mockResolvedValue({ plan: "pro" });
    fetchQueryMock.mockImplementation(() => Promise.resolve({ plan: "pro" }));
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
    await waitFor(() => {
      expect(invalidateQueriesMock).toHaveBeenCalledWith({
        queryKey: ["current-user"],
      });
      expect(fetchQueryMock).toHaveBeenCalled();
      expect(setPlanMock).toHaveBeenCalledWith("pro");
    });

    await waitFor(() => {
      expect(logSubscriptionEventMock).toHaveBeenCalledWith(
        expect.objectContaining({ action: "refresh_start" })
      );
      expect(logSubscriptionEventMock).toHaveBeenCalledWith(
        expect.objectContaining({ action: "refresh_success" })
      );
    });

    const startCalls = logSubscriptionEventMock.mock.calls.filter(
      ([payload]) => (payload as { action?: string }).action === "refresh_start"
    );
    const successCalls = logSubscriptionEventMock.mock.calls.filter(
      ([payload]) =>
        (payload as { action?: string }).action === "refresh_success"
    );
    const errorCalls = logSubscriptionEventMock.mock.calls.filter(
      ([payload]) => (payload as { action?: string }).action === "refresh_error"
    );

    expect(startCalls).toHaveLength(1);
    expect(successCalls).toHaveLength(1);
    expect(errorCalls).toHaveLength(0);

    const proSetCalls = setPlanMock.mock.calls.filter(
      ([plan]) => plan === "pro"
    );
    expect(proSetCalls.length).toBeGreaterThanOrEqual(2);
  });

  it("notes missing session id and logs message", async () => {
    const { setTimeoutSpy, clearTimeoutSpy } = mockImmediateTimeouts();
    locationSearchRef.current = "";
    fetchQueryMock.mockReset();

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
      screen.getByText(/could not verify a recent checkout/i)
    ).toBeInTheDocument();

    expect(navigateMock).toHaveBeenCalledWith({
      to: "/billing",
      replace: true,
    });

    expect(logSubscriptionEventMock).not.toHaveBeenCalled();

    setTimeoutSpy.mockRestore();
    clearTimeoutSpy.mockRestore();
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
