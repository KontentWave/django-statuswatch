import {
  afterAll,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import LoginPage from "@/pages/Login";

const assignMock = vi.fn();

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
        searchStr: "",
        publicHref: "/login",
        url: new URL("http://localhost/login"),
        state: locationState.current,
      } as unknown as ReturnType<typeof actual.useLocation>),
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

const originalLocation = window.location;

beforeAll(() => {
  Object.defineProperty(window, "location", {
    configurable: true,
    value: {
      ...originalLocation,
      assign: assignMock,
      replace: vi.fn(),
      reload: vi.fn(),
      protocol: "https:",
      host: "localhost:5173",
      hostname: "localhost",
      port: "5173",
      href: "https://localhost:5173/login",
      pathname: "/login",
      search: "",
      hash: "",
      origin: "https://localhost:5173",
    },
  });
});

afterAll(() => {
  Object.defineProperty(window, "location", {
    configurable: true,
    value: originalLocation,
  });
});

describe("LoginPage", () => {
  beforeEach(() => {
    postMock.mockReset();
    navigateMock.mockReset();
    storeTokensMock.mockReset();
    locationState.current = undefined;
    assignMock.mockReset();
    window.location.hash = "";
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
        tenant_domain: undefined,
      },
    });

    locationState.current = { redirectTo: "/dashboard" };

    render(<LoginPage />);

    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/email/i), "user@example.com");
    await user.type(screen.getByLabelText(/password/i), "Password123!");

    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(postMock).toHaveBeenCalledWith("/auth/login/", {
        username: "user@example.com",
        password: "Password123!",
        tenant_schema: null,
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

    expect(assignMock).not.toHaveBeenCalled();
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

  it("redirects to tenant login for session transfer when tenant domain provided", async () => {
    postMock.mockResolvedValue({
      data: {
        access: "access-token",
        refresh: "refresh-token",
        tenant_domain: "acme.localhost",
        tenant_schema: "acme",
        tenant_name: "Acme",
      },
    });

    render(<LoginPage />);

    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/email/i), "user@example.com");
    await user.type(screen.getByLabelText(/password/i), "Password123!");

    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(storeTokensMock).toHaveBeenCalledWith({
        access: "access-token",
        refresh: "refresh-token",
      });
    });

    await waitFor(() => {
      expect(assignMock).toHaveBeenCalledTimes(1);
    });

    const targetUrl = assignMock.mock.calls[0]?.[0] as string;
    expect(targetUrl).toMatch(
      /^https:\/\/acme\.localhost:5173\/login#session=/
    );
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

  it("consumes session transfer payload from hash on mount", async () => {
    const payload = {
      access: "hash-access",
      refresh: "hash-refresh",
      tenant_schema: "acme",
      tenant_name: "Acme",
      source: "login_page",
    };
    window.location.hash = `session=${btoa(
      JSON.stringify(payload)
    )}&source=login_page`;

    render(<LoginPage />);

    await waitFor(() => {
      expect(storeTokensMock).toHaveBeenCalledWith({
        access: "hash-access",
        refresh: "hash-refresh",
      });
    });

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith({
        to: "/dashboard",
        replace: true,
      });
    });

    expect(assignMock).not.toHaveBeenCalled();

    window.location.hash = "";
  });

  it("navigates locally when tenant domain matches current origin", async () => {
    postMock.mockResolvedValue({
      data: {
        access: "access-token",
        refresh: "refresh-token",
        tenant_domain: "localhost:5173",
      },
    });

    render(<LoginPage />);

    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/email/i), "user@example.com");
    await user.type(screen.getByLabelText(/password/i), "Password123!");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

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

    expect(assignMock).not.toHaveBeenCalled();
  });
});
