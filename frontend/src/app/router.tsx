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
]);

const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

export function AppRouter() {
  return <RouterProvider router={router} />;
}
