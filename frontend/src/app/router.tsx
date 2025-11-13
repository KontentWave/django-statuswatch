import {
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
  redirect,
} from "@tanstack/react-router";
import Home from "@/pages/Home";
import LoginPage from "@/pages/Login";
import RegisterPage from "@/pages/Register";
import DashboardPage from "@/pages/Dashboard";
import BillingPage from "@/pages/Billing";
import BillingSuccessPage from "@/pages/BillingSuccess";
import BillingCancelPage from "@/pages/BillingCancel";
import { getAccessToken } from "@/lib/auth";

/**
 * Check if current domain is the public domain (not a tenant subdomain)
 * - localhost / 127.0.0.1 = public (dev)
 * - statuswatch.kontentwave.digital = public (prod)
 * - acme.statuswatch.kontentwave.digital = tenant subdomain
 */
function isPublicDomain(): boolean {
  const hostname = window.location.hostname;

  // Development: localhost is public domain
  if (hostname === "localhost" || hostname === "127.0.0.1") {
    return true;
  }

  // Production: check if we're on the root domain (no subdomain prefix)
  // Count dots: statuswatch.kontentwave.digital has 2 dots (public)
  //            acme.statuswatch.kontentwave.digital has 3 dots (tenant)
  const parts = hostname.split(".");

  // If hostname is exactly "statuswatch.kontentwave.digital" (3 parts), it's public
  // If it has more parts (e.g., "acme.statuswatch.kontentwave.digital"), it's a tenant
  if (parts.length === 3 && parts[0] === "statuswatch") {
    return true; // Public domain
  }

  return false; // Tenant subdomain
}

/**
 * Route guard for public domain - only allow /, /login, and /register
 */
function guardPublicDomain(pathname: string) {
  if (!isPublicDomain()) {
    return; // Allow all routes on tenant subdomains
  }

  const allowedPaths = ["/", "/login", "/register"];
  if (!allowedPaths.includes(pathname)) {
    throw redirect({
      to: "/",
      replace: true,
    });
  }
}

const rootRoute = createRootRoute();
const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: Home,
});
const registerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/register",
  component: RegisterPage,
});
const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  component: LoginPage,
});
const authenticatedRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: "authenticated",
  beforeLoad: ({ location }) => {
    // First check if we're on public domain trying to access protected routes
    guardPublicDomain(location.pathname);

    // Then check authentication
    if (getAccessToken()) {
      return;
    }

    throw redirect({
      to: "/login",
      replace: true,
      state: (prev) =>
        ({
          ...(typeof prev === "object" && prev !== null ? prev : {}),
          message: "Please sign in to continue.",
          redirectTo: (location.pathname ?? "/dashboard") as "/dashboard",
        } as Record<string, unknown>),
    });
  },
});
const dashboardRoute = createRoute({
  getParentRoute: () => authenticatedRoute,
  path: "/dashboard",
  component: DashboardPage,
});
const billingRoute = createRoute({
  getParentRoute: () => authenticatedRoute,
  path: "/billing",
  component: BillingPage,
});
const billingSuccessRoute = createRoute({
  getParentRoute: () => authenticatedRoute,
  path: "/billing/success",
  component: BillingSuccessPage,
});
const billingCancelRoute = createRoute({
  getParentRoute: () => authenticatedRoute,
  path: "/billing/cancel",
  component: BillingCancelPage,
});

// Catch-all route for undefined paths
const notFoundRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "*",
  beforeLoad: () => {
    throw redirect({
      to: "/",
      replace: true,
    });
  },
  component: () => null, // This won't render due to redirect
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  registerRoute,
  loginRoute,
  authenticatedRoute.addChildren([
    dashboardRoute,
    billingRoute,
    billingSuccessRoute,
    billingCancelRoute,
  ]),
  notFoundRoute, // Must be last
]);

const router = createRouter({
  routeTree,
  defaultNotFoundComponent: () => {
    // Redirect to home on any not-found route
    window.location.href = "/";
    return null;
  },
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

export function AppRouter() {
  return <RouterProvider router={router} />;
}
