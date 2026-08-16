import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import VerifyEmailPage from "@/pages/VerifyEmail";

const { postMock, locationSearch, navigateMock } = vi.hoisted(() => ({
  postMock: vi.fn(),
  locationSearch: { current: "?token=test-token" },
  navigateMock: vi.fn(),
}));

vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual<typeof import("@tanstack/react-router")>(
    "@tanstack/react-router"
  );
  return {
    ...actual,
    useLocation: () =>
      ({
        pathname: "/verify-email",
        search: locationSearch.current,
        href: `/verify-email${locationSearch.current}`,
        hash: "",
        key: "verify",
        params: {},
        searchStr: locationSearch.current,
        publicHref: `/verify-email${locationSearch.current}`,
        url: new URL(
          `https://localhost:5173/verify-email${locationSearch.current}`
        ),
        state: undefined,
      } as unknown as ReturnType<typeof actual.useLocation>),
    useNavigate: () => navigateMock,
  };
});

vi.mock("@/lib/api", () => ({
  api: {
    post: postMock,
  },
}));

describe("VerifyEmailPage", () => {
  beforeEach(() => {
    postMock.mockReset();
    navigateMock.mockReset();
    locationSearch.current = "?token=test-token";
    window.sessionStorage.clear();
  });

  it("verifies the token from the query string and shows success state", async () => {
    postMock.mockResolvedValueOnce({
      data: { detail: "Email verified", email: "user@example.com" },
    });

    render(<VerifyEmailPage />);

    await waitFor(() => {
      expect(postMock).toHaveBeenCalled();
    });

    const [endpoint, payload] = postMock.mock.calls[0];
    expect(endpoint).toBe("/auth/verify-email/");
    expect(payload).toEqual({ token: "test-token" });

    expect(
      await screen.findByRole("heading", { name: /email verified/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /continue to dashboard/i })
    ).toBeVisible();
  });

  it("renders error state and allows resending when verification fails", async () => {
    postMock.mockRejectedValueOnce({
      response: {
        status: 400,
        data: {
          error: "Verification token expired",
          expired: true,
          email: "user@example.com",
        },
      },
    });
    postMock.mockResolvedValueOnce({ data: { detail: "Resent" } });

    render(<VerifyEmailPage />);

    const user = userEvent.setup();

    expect(
      await screen.findByText(
        /verification token expired/i,
        {},
        { timeout: 3000 }
      )
    ).toBeInTheDocument();

    const resendButton = screen.getByRole("button", { name: /resend link/i });
    await user.click(resendButton);

    const resendCall = postMock.mock.calls.find(
      ([endpoint]) => endpoint === "/auth/resend-verification/"
    );
    expect(resendCall).toBeTruthy();
    expect(resendCall?.[1]).toEqual({ email: "user@example.com" });
  });

  it("shows an error when no token is present", () => {
    locationSearch.current = "";

    render(<VerifyEmailPage />);

    expect(
      screen.getByText(/verification token missing/i, { exact: false })
    ).toBeInTheDocument();
    expect(postMock).not.toHaveBeenCalled();
  });

  it("reuses cached verification results when the component re-renders with the same token", async () => {
    postMock.mockResolvedValueOnce({
      data: {
        detail: "Email verified",
        email: "cached@example.com",
      },
    });

    const { rerender } = render(<VerifyEmailPage />);

    expect(
      await screen.findByRole("heading", { name: /email verified/i })
    ).toBeInTheDocument();
    expect(postMock).toHaveBeenCalledTimes(1);

    postMock.mockClear();

    rerender(<VerifyEmailPage />);

    expect(
      await screen.findByRole("heading", { name: /email verified/i })
    ).toBeInTheDocument();
    expect(postMock).not.toHaveBeenCalled();
  });

  it("navigates back to login with the intended redirect path", async () => {
    locationSearch.current = "?token=test-token&next=/billing";
    postMock.mockResolvedValueOnce({
      data: { detail: "Email verified", email: "user@example.com" },
    });

    render(<VerifyEmailPage />);

    const user = userEvent.setup();

    await user.click(
      await screen.findByRole("button", { name: /continue to dashboard/i })
    );

    expect(navigateMock).toHaveBeenCalledWith(
      expect.objectContaining({
        replace: true,
        state: expect.any(Function),
        search: expect.any(Function),
        to: "/login",
      })
    );

    const navigateArgs = navigateMock.mock.calls[0][0];

    const stateUpdater = navigateArgs.state as (prev: unknown) => unknown;
    const result = stateUpdater(undefined) as {
      redirectTo?: string;
      message?: string;
    };
    expect(result.redirectTo).toBe("/billing");
    expect(result.message).toContain("Email verified");

    const searchUpdater = navigateArgs.search as (prev: unknown) => {
      redirect?: string;
    };
    const searchResult = searchUpdater(undefined);
    expect(searchResult.redirect).toBe("/billing");
  });
});
