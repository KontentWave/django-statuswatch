import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import RegisterPage from "@/pages/Register";

const { navigateMock, postMock } = vi.hoisted(() => ({
  navigateMock: vi.fn(),
  postMock: vi.fn(),
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
  api: {
    post: postMock,
  },
}));

describe("RegisterPage", () => {
  beforeEach(() => {
    postMock.mockReset();
    navigateMock.mockReset();
  });

  it("shows an error when passwords do not match", async () => {
    postMock.mockResolvedValue({ data: { detail: "will not be used" } });

    render(<RegisterPage />);

    const user = userEvent.setup();

    await user.type(
      screen.getByLabelText(/organization name/i),
      "Stark Industries"
    );
    await user.type(screen.getByLabelText(/email/i), "tony@stark.com");
    await user.type(screen.getByLabelText(/^password$/i), "JarvisIsMyP@ssw0rd");
    await user.type(screen.getByLabelText(/confirm password/i), "Mismatch123");

    await user.click(screen.getByRole("button", { name: /sign up/i }));

    expect(
      await screen.findByText(/passwords must match/i)
    ).toBeInTheDocument();
    expect(postMock).not.toHaveBeenCalled();
  });

  it("submits form data and navigates to login on success", async () => {
    postMock.mockResolvedValue({
      data: { detail: "Registration successful. Please log in." },
    });

    render(<RegisterPage />);

    const user = userEvent.setup();

    await user.type(
      screen.getByLabelText(/organization name/i),
      "Stark Industries"
    );
    await user.type(screen.getByLabelText(/email/i), "tony@stark.com");
    await user.type(screen.getByLabelText(/^password$/i), "JarvisIsMyP@ssw0rd");
    await user.type(
      screen.getByLabelText(/confirm password/i),
      "JarvisIsMyP@ssw0rd"
    );

    await user.click(screen.getByRole("button", { name: /sign up/i }));

    await waitFor(() => {
      expect(postMock).toHaveBeenCalledWith("/auth/register/", {
        organization_name: "Stark Industries",
        email: "tony@stark.com",
        password: "JarvisIsMyP@ssw0rd",
        password_confirm: "JarvisIsMyP@ssw0rd",
      });
    });

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledTimes(1);
    });

    const navigationArgs = navigateMock.mock.calls[0][0];
    expect(navigationArgs.to).toBe("/login");
    expect(navigationArgs.replace).toBe(true);
    expect(typeof navigationArgs.state).toBe("function");
    expect(navigationArgs.state(undefined)).toEqual({
      message: "Registration successful. Please log in.",
    });
  });

  it("shows API validation errors returned from the backend", async () => {
    postMock.mockRejectedValue({
      response: {
        status: 400,
        data: {
          errors: {
            email: ["This email is already registered."],
          },
        },
      },
    });

    render(<RegisterPage />);

    const user = userEvent.setup();

    await user.type(
      screen.getByLabelText(/organization name/i),
      "Stark Industries"
    );
    await user.type(screen.getByLabelText(/email/i), "tony@stark.com");
    await user.type(screen.getByLabelText(/^password$/i), "JarvisIsMyP@ssw0rd");
    await user.type(
      screen.getByLabelText(/confirm password/i),
      "JarvisIsMyP@ssw0rd"
    );

    await user.click(screen.getByRole("button", { name: /sign up/i }));

    expect(
      await screen.findByText(/this email is already registered/i)
    ).toBeInTheDocument();
    expect(navigateMock).not.toHaveBeenCalled();
  });
});
