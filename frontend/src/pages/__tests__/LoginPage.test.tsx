import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import LoginPage from "@/pages/Login";

const { navigateMock, postMock, storeTokensMock, locationState } = vi.hoisted(
  () => ({
    navigateMock: vi.fn(),
    postMock: vi.fn(),
    storeTokensMock: vi.fn(),
    locationState: { current: undefined as unknown },
  })
);

vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual<typeof import("@tanstack/react-router")>(
    "@tanstack/react-router"
  );
  return {
    ...actual,
    useNavigate: () => navigateMock,
    useLocation: () =>
      ({
        pathname: "/login",
        search: "",
        hash: "",
        key: "test",
        params: {},
        href: "/login",
        state: locationState.current,
      } as ReturnType<typeof actual.useLocation>),
  };
});

vi.mock("@/lib/api", () => ({
  api: {
    post: postMock,
  },
}));

vi.mock("@/lib/auth", () => ({
  storeAuthTokens: storeTokensMock,
}));

describe("LoginPage", () => {
  beforeEach(() => {
    postMock.mockReset();
    navigateMock.mockReset();
    storeTokensMock.mockReset();
    locationState.current = undefined;
  });

  it("requires email and password", async () => {
    render(<LoginPage />);

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/email is required/i)).toBeInTheDocument();
    expect(
      await screen.findByText(/password is required/i)
    ).toBeInTheDocument();
    expect(postMock).not.toHaveBeenCalled();
  });

  it("stores tokens and navigates on successful login", async () => {
    postMock.mockResolvedValue({
      data: {
        access: "access-token",
        refresh: "refresh-token",
      },
    });

    locationState.current = { redirectTo: "/dashboard" };

    render(<LoginPage />);

    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/email/i), "user@example.com");
    await user.type(screen.getByLabelText(/password/i), "Password123!");

    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(postMock).toHaveBeenCalledWith("/auth/token/", {
        username: "user@example.com",
        password: "Password123!",
      });
    });

    await waitFor(() => {
      expect(storeTokensMock).toHaveBeenCalledWith({
        access: "access-token",
        refresh: "refresh-token",
      });
    });

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith({
        to: "/dashboard",
        replace: true,
      });
    });
  });

  it("shows API error message when credentials are invalid", async () => {
    postMock.mockRejectedValue({
      response: {
        status: 401,
        data: { detail: "No active account found with the given credentials" },
      },
    });

    render(<LoginPage />);

    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/email/i), "user@example.com");
    await user.type(screen.getByLabelText(/password/i), "BadPassword123!");

    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(
      await screen.findByText(
        /no active account found with the given credentials/i
      )
    ).toBeInTheDocument();
    expect(storeTokensMock).not.toHaveBeenCalled();
    expect(navigateMock).not.toHaveBeenCalled();
  });

  it("renders registration success message from navigation state", () => {
    locationState.current = {
      message: "Registration successful. Please log in.",
    };

    render(<LoginPage />);

    expect(
      screen.getByText(/registration successful\. please log in\./i)
    ).toBeInTheDocument();
  });
});
