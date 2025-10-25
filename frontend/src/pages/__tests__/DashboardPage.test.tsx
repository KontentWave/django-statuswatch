import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { AxiosError } from "axios";

import DashboardPage from "@/pages/Dashboard";

const {
  fetchCurrentUserMock,
  submitLogoutMock,
  navigateMock,
  clearAuthTokensMock,
  getRefreshTokenMock,
  listEndpointsMock,
  createEndpointMock,
  deleteEndpointMock,
  logDashboardEventMock,
} = vi.hoisted(() => ({
  fetchCurrentUserMock: vi.fn(),
  submitLogoutMock: vi.fn(),
  navigateMock: vi.fn(),
  clearAuthTokensMock: vi.fn(),
  getRefreshTokenMock: vi.fn(),
  listEndpointsMock: vi.fn(),
  createEndpointMock: vi.fn(),
  deleteEndpointMock: vi.fn(),
  logDashboardEventMock: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  fetchCurrentUser: () => fetchCurrentUserMock(),
  submitLogout: (refresh: string) => submitLogoutMock(refresh),
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

vi.mock("@/lib/auth", () => ({
  clearAuthTokens: () => clearAuthTokensMock(),
  getRefreshToken: () => getRefreshTokenMock(),
}));

vi.mock("@/lib/endpoint-client", () => ({
  listEndpoints: (params?: unknown) => listEndpointsMock(params),
  createEndpoint: (payload: unknown) => createEndpointMock(payload),
  deleteEndpoint: (endpointId: string) => deleteEndpointMock(endpointId),
}));

vi.mock("@/lib/dashboard-logger", () => ({
  logDashboardEvent: (payload: unknown) => logDashboardEventMock(payload),
}));

function renderDashboard() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <DashboardPage />
    </QueryClientProvider>
  );
}

describe("DashboardPage", () => {
  beforeEach(() => {
    fetchCurrentUserMock.mockReset();
    submitLogoutMock.mockReset();
    navigateMock.mockReset();
    clearAuthTokensMock.mockReset();
    getRefreshTokenMock.mockReset();
    getRefreshTokenMock.mockReturnValue("refresh-token");
    listEndpointsMock.mockReset();
    createEndpointMock.mockReset();
    deleteEndpointMock.mockReset();
    logDashboardEventMock.mockReset();
    listEndpointsMock.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    });
  });

  it("shows current user details when /auth/me/ succeeds", async () => {
    fetchCurrentUserMock.mockResolvedValue({
      id: 1,
      username: "tony",
      email: "tony@stark.com",
      first_name: "Tony",
      last_name: "Stark",
      is_staff: false,
      date_joined: "2025-01-01T12:00:00Z",
      groups: ["Owner"],
    });

    renderDashboard();

    expect(
      await screen.findByText(/you are signed in as/i)
    ).toBeInTheDocument();
    await waitFor(() => expect(listEndpointsMock).toHaveBeenCalled());
    expect(screen.getByText(/tony@stark.com/i)).toBeInTheDocument();
    expect(fetchCurrentUserMock).toHaveBeenCalledTimes(1);
    expect(navigateMock).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(logDashboardEventMock).toHaveBeenCalledWith(
        expect.objectContaining({
          event: "pagination",
          phase: "success",
          page: 1,
        })
      )
    );
  });

  it("clears tokens and redirects to login on 401", async () => {
    const axiosError = {
      name: "AxiosError",
      message: "Unauthorized",
      toJSON: () => ({}),
      isAxiosError: true,
      response: {
        status: 401,
      },
    } as AxiosError;

    fetchCurrentUserMock.mockRejectedValue(axiosError);

    renderDashboard();

    await waitFor(() => {
      expect(clearAuthTokensMock).toHaveBeenCalledTimes(1);
    });

    expect(navigateMock).toHaveBeenCalledWith({
      to: "/login",
      replace: true,
      state: expect.any(Function),
    });
  });

  it("sends logout request, clears tokens, and navigates to login", async () => {
    fetchCurrentUserMock.mockResolvedValue({
      id: 1,
      username: "tony",
      email: "tony@stark.com",
      first_name: "Tony",
      last_name: "Stark",
      is_staff: false,
      date_joined: "2025-01-01T12:00:00Z",
      groups: ["Owner"],
    });

    submitLogoutMock.mockResolvedValue({});

    renderDashboard();

    expect(
      await screen.findByText(/you are signed in as/i)
    ).toBeInTheDocument();
    await waitFor(() => expect(listEndpointsMock).toHaveBeenCalled());

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /log out/i }));

    await waitFor(() => {
      expect(submitLogoutMock).toHaveBeenCalledWith("refresh-token");
    });

    expect(clearAuthTokensMock).toHaveBeenCalledTimes(1);
    expect(navigateMock).toHaveBeenCalledWith({
      to: "/login",
      replace: true,
      state: expect.any(Function),
    });

    const navState = navigateMock.mock.calls[0][0].state({});
    expect(navState.message).toBe("You have been logged out.");
  });

  it("shows a helpful message when logout fails", async () => {
    fetchCurrentUserMock.mockResolvedValue({
      id: 1,
      username: "tony",
      email: "tony@stark.com",
      first_name: "Tony",
      last_name: "Stark",
      is_staff: false,
      date_joined: "2025-01-01T12:00:00Z",
      groups: ["Owner"],
    });

    submitLogoutMock.mockRejectedValue(new Error("Server unavailable"));

    renderDashboard();

    expect(
      await screen.findByText(/you are signed in as/i)
    ).toBeInTheDocument();
    await waitFor(() => expect(listEndpointsMock).toHaveBeenCalled());

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /log out/i }));

    expect(await screen.findByText(/server unavailable/i)).toBeInTheDocument();
    expect(clearAuthTokensMock).not.toHaveBeenCalled();
    expect(navigateMock).not.toHaveBeenCalled();
  });

  it("displays endpoints from the API", async () => {
    fetchCurrentUserMock.mockResolvedValue({
      id: 1,
      username: "tony",
      email: "tony@stark.com",
      first_name: "Tony",
      last_name: "Stark",
      is_staff: false,
      date_joined: "2025-01-01T12:00:00Z",
      groups: ["Owner"],
    });

    listEndpointsMock.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: "ep-1",
          name: "API",
          url: "https://example.com/health",
          interval_minutes: 5,
          last_status: "ok",
          last_checked_at: "2025-10-22T10:00:00Z",
          last_latency_ms: 120,
          last_enqueued_at: "2025-10-22T10:01:00Z",
          created_at: "2025-10-22T09:00:00Z",
          updated_at: "2025-10-22T10:01:00Z",
        },
      ],
    });

    renderDashboard();

    expect(await screen.findByText(/monitored endpoints/i)).toBeInTheDocument();
    expect(
      await screen.findByText("https://example.com/health")
    ).toBeInTheDocument();
    expect(screen.getByText(/ok/i)).toBeInTheDocument();
    await waitFor(() =>
      expect(logDashboardEventMock).toHaveBeenCalledWith(
        expect.objectContaining({
          event: "pagination",
          phase: "success",
          page: 1,
        })
      )
    );
  });

  it("navigates to billing when requested", async () => {
    fetchCurrentUserMock.mockResolvedValue({
      id: 1,
      username: "tony",
      email: "tony@stark.com",
      first_name: "Tony",
      last_name: "Stark",
      is_staff: false,
      date_joined: "2025-01-01T12:00:00Z",
      groups: ["Owner"],
    });

    renderDashboard();

    expect(
      await screen.findByText(/you are signed in as/i)
    ).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /manage billing/i }));

    expect(navigateMock).toHaveBeenCalledWith({ to: "/billing" });
  });

  it("logs pagination events when changing pages", async () => {
    fetchCurrentUserMock.mockResolvedValue({
      id: 1,
      username: "tony",
      email: "tony@stark.com",
      first_name: "Tony",
      last_name: "Stark",
      is_staff: false,
      date_joined: "2025-01-01T12:00:00Z",
      groups: ["Owner"],
    });

    const firstPage = {
      count: 3,
      next: "/api/endpoints/?page=2",
      previous: null,
      results: [
        {
          id: "ep-1",
          name: "API",
          url: "https://example.com/health",
          interval_minutes: 5,
          last_status: "ok",
          last_checked_at: "2025-10-22T10:00:00Z",
          last_latency_ms: 120,
          last_enqueued_at: "2025-10-22T10:01:00Z",
          created_at: "2025-10-22T09:00:00Z",
          updated_at: "2025-10-22T10:01:00Z",
        },
        {
          id: "ep-2",
          name: "Billing API",
          url: "https://example.com/billing",
          interval_minutes: 10,
          last_status: "pending",
          last_checked_at: null,
          last_latency_ms: null,
          last_enqueued_at: "2025-10-22T11:00:00Z",
          created_at: "2025-10-22T11:00:00Z",
          updated_at: "2025-10-22T11:00:00Z",
        },
      ],
    } as const;

    const secondPage = {
      count: 3,
      next: null,
      previous: "/api/endpoints/?page=1",
      results: [
        {
          id: "ep-3",
          name: "Status API",
          url: "https://example.com/status",
          interval_minutes: 15,
          last_status: "ok",
          last_checked_at: "2025-10-22T11:30:00Z",
          last_latency_ms: 95,
          last_enqueued_at: "2025-10-22T11:35:00Z",
          created_at: "2025-10-22T10:30:00Z",
          updated_at: "2025-10-22T11:35:00Z",
        },
      ],
    } as const;

    listEndpointsMock.mockImplementation(
      ({ page }: { page?: number } = { page: 1 }) =>
        Promise.resolve(page === 2 ? secondPage : firstPage)
    );

    renderDashboard();

    expect(
      await screen.findByText("https://example.com/health")
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(logDashboardEventMock).toHaveBeenCalledWith(
        expect.objectContaining({
          event: "pagination",
          phase: "success",
          page: 1,
        })
      )
    );

    expect(
      screen.getByText((content) => /page\s+1\s+of\s+2/i.test(content))
    ).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /next/i }));

    await waitFor(() =>
      expect(logDashboardEventMock).toHaveBeenCalledWith(
        expect.objectContaining({
          event: "pagination",
          phase: "start",
          page: 2,
        })
      )
    );

    expect(
      await screen.findByText("https://example.com/status")
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(logDashboardEventMock).toHaveBeenCalledWith(
        expect.objectContaining({
          event: "pagination",
          phase: "success",
          page: 2,
        })
      )
    );
    expect(
      screen.getByText((content) => /page\s+2\s+of\s+2/i.test(content))
    ).toBeInTheDocument();
  });

  it("creates a new endpoint and refreshes the list", async () => {
    fetchCurrentUserMock.mockResolvedValue({
      id: 1,
      username: "tony",
      email: "tony@stark.com",
      first_name: "Tony",
      last_name: "Stark",
      is_staff: false,
      date_joined: "2025-01-01T12:00:00Z",
      groups: ["Owner"],
    });

    listEndpointsMock
      .mockResolvedValueOnce({
        count: 0,
        next: null,
        previous: null,
        results: [],
      })
      .mockResolvedValueOnce({
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            id: "ep-2",
            name: "Billing API",
            url: "https://example.com/billing",
            interval_minutes: 10,
            last_status: "pending",
            last_checked_at: null,
            last_latency_ms: null,
            last_enqueued_at: "2025-10-22T11:00:00Z",
            created_at: "2025-10-22T11:00:00Z",
            updated_at: "2025-10-22T11:00:00Z",
          },
        ],
      });

    createEndpointMock.mockResolvedValue({
      id: "ep-2",
      name: "Billing API",
      url: "https://example.com/billing",
      interval_minutes: 10,
      last_status: "pending",
      last_checked_at: null,
      last_latency_ms: null,
      last_enqueued_at: "2025-10-22T11:00:00Z",
      created_at: "2025-10-22T11:00:00Z",
      updated_at: "2025-10-22T11:00:00Z",
    });

    renderDashboard();

    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/name \(optional\)/i), "Billing API");
    await user.type(
      screen.getByLabelText(/url/i),
      "https://example.com/billing"
    );
    const intervalInput = screen.getByLabelText(/interval \(minutes\)/i);
    await user.clear(intervalInput);
    await user.type(intervalInput, "10");

    await user.click(screen.getByRole("button", { name: /add endpoint/i }));

    await waitFor(() => {
      expect(createEndpointMock).toHaveBeenCalledWith({
        name: "Billing API",
        url: "https://example.com/billing",
        interval_minutes: 10,
      });
    });

    expect(
      await screen.findByText("https://example.com/billing")
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(logDashboardEventMock).toHaveBeenCalledWith(
        expect.objectContaining({
          event: "pagination",
          phase: "success",
          page: 1,
        })
      )
    );
  });

  it("deletes an endpoint and refreshes the list", async () => {
    fetchCurrentUserMock.mockResolvedValue({
      id: 1,
      username: "tony",
      email: "tony@stark.com",
      first_name: "Tony",
      last_name: "Stark",
      is_staff: false,
      date_joined: "2025-01-01T12:00:00Z",
      groups: ["Owner"],
    });

    listEndpointsMock
      .mockResolvedValueOnce({
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            id: "ep-3",
            name: "API",
            url: "https://example.com/health",
            interval_minutes: 5,
            last_status: "ok",
            last_checked_at: "2025-10-22T10:00:00Z",
            last_latency_ms: 120,
            last_enqueued_at: "2025-10-22T10:01:00Z",
            created_at: "2025-10-22T09:00:00Z",
            updated_at: "2025-10-22T10:01:00Z",
          },
        ],
      })
      .mockResolvedValueOnce({
        count: 0,
        next: null,
        previous: null,
        results: [],
      });

    deleteEndpointMock.mockResolvedValue({ endpointId: "ep-3" });

    renderDashboard();

    expect(
      await screen.findByText("https://example.com/health")
    ).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /delete/i }));

    await waitFor(() => {
      expect(deleteEndpointMock).toHaveBeenCalledWith("ep-3");
    });

    await waitFor(() => {
      expect(
        screen.queryByText("https://example.com/health")
      ).not.toBeInTheDocument();
    });
    await waitFor(() =>
      expect(logDashboardEventMock).toHaveBeenCalledWith(
        expect.objectContaining({
          event: "pagination",
          phase: "success",
          page: 1,
        })
      )
    );
  });

  it("shows create error feedback", async () => {
    fetchCurrentUserMock.mockResolvedValue({
      id: 1,
      username: "tony",
      email: "tony@stark.com",
      first_name: "Tony",
      last_name: "Stark",
      is_staff: false,
      date_joined: "2025-01-01T12:00:00Z",
      groups: ["Owner"],
    });

    const error = new Error("Validation failed");
    createEndpointMock.mockRejectedValue(error);

    renderDashboard();

    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/url/i), "https://example.com/bad");
    await user.click(screen.getByRole("button", { name: /add endpoint/i }));

    expect(await screen.findByText(/validation failed/i)).toBeInTheDocument();
  });
});
