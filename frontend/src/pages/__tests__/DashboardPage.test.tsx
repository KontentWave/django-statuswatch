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
} = vi.hoisted(() => ({
  fetchCurrentUserMock: vi.fn(),
  submitLogoutMock: vi.fn(),
  navigateMock: vi.fn(),
  clearAuthTokensMock: vi.fn(),
  getRefreshTokenMock: vi.fn(),
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
    expect(screen.getByText(/tony@stark.com/i)).toBeInTheDocument();
    expect(fetchCurrentUserMock).toHaveBeenCalledTimes(1);
    expect(navigateMock).not.toHaveBeenCalled();
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

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /log out/i }));

    expect(await screen.findByText(/server unavailable/i)).toBeInTheDocument();
    expect(clearAuthTokensMock).not.toHaveBeenCalled();
    expect(navigateMock).not.toHaveBeenCalled();
  });
});
