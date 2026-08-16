import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";

import { AuthPage } from "../pages/auth-page";
import { buildRegistrationInput } from "../support/registration-data";

test.describe("Advanced registration & verification", () => {
  test("user must verify email before logging in", async ({
    page,
    request,
  }) => {
    const registration = buildRegistrationInput();
    const authPage = new AuthPage(page);

    await authPage.gotoRegister();
    await authPage.completeRegistration(registration);

    await attemptLogin(page, registration.email, registration.password);
    await expect(page.getByText(/email not verified/i)).toBeVisible();

    const token = await fetchLatestVerificationToken(
      request,
      registration.email,
    );

    await page.goto(`/verify-email?token=${token}`);
    await expect(
      page.getByRole("heading", { name: /email verified/i }),
    ).toBeVisible();
    await page.getByRole("button", { name: /continue to login/i }).click();
    await expect(page).toHaveURL(/\/login/);

    await attemptLogin(page, registration.email, registration.password);
    await page.waitForURL(/\/dashboard/);
  });

  test("resending verification invalidates older links", async ({
    page,
    request,
  }) => {
    const registration = buildRegistrationInput();
    const authPage = new AuthPage(page);

    await authPage.gotoRegister();
    await authPage.completeRegistration(registration);

    await attemptLogin(page, registration.email, registration.password);
    await expect(page.getByText(/email not verified/i)).toBeVisible();

    const firstToken = await fetchLatestVerificationToken(
      request,
      registration.email,
    );

    await page
      .getByRole("button", { name: /resend verification email/i })
      .click();
    await expect(page.getByText(/fresh verification link/i)).toBeVisible();

    const secondToken = await fetchLatestVerificationToken(
      request,
      registration.email,
    );
    expect(secondToken).not.toBe(firstToken);

    await page.goto(`/verify-email?token=${firstToken}`);
    await expect(page.getByText(/invalid verification token/i)).toBeVisible();

    await page.goto(`/verify-email?token=${secondToken}`);
    await expect(
      page.getByRole("heading", { name: /email verified/i }),
    ).toBeVisible();
  });

  test("expired tokens surface errors and can be refreshed", async ({
    page,
    request,
  }) => {
    const registration = buildRegistrationInput();
    const authPage = new AuthPage(page);

    await authPage.gotoRegister();
    await authPage.completeRegistration(registration);

    await attemptLogin(page, registration.email, registration.password);
    await expect(page.getByText(/email not verified/i)).toBeVisible();

    const originalToken = await fetchLatestVerificationToken(
      request,
      registration.email,
    );

    await expireVerificationToken(request, registration.email);

    await page.goto(`/verify-email?token=${originalToken}`);
    await expect(page.getByText(/token has expired/i)).toBeVisible();

    await page.getByRole("button", { name: /resend link/i }).click();
    await expect(page.getByText(/fresh verification link/i)).toBeVisible();

    const refreshedToken = await fetchLatestVerificationToken(
      request,
      registration.email,
    );

    await page.goto(`/verify-email?token=${refreshedToken}`);
    await page.getByRole("button", { name: /continue to login/i }).click();

    await attemptLogin(page, registration.email, registration.password);
    await page.waitForURL(/\/dashboard/);
  });

  test("verification flow preserves redirect targets", async ({
    page,
    request,
  }) => {
    const registration = buildRegistrationInput();
    const authPage = new AuthPage(page);

    await authPage.gotoRegister();
    await authPage.completeRegistration(registration);

    await page.goto("/billing");
    await expect(page).toHaveURL(/\/login/);

    await attemptLogin(page, registration.email, registration.password);
    await expect(page.getByText(/email not verified/i)).toBeVisible();

    const token = await fetchLatestVerificationToken(
      request,
      registration.email,
    );

    await page.goto(`/verify-email?token=${token}&next=/billing`);
    await page.getByRole("button", { name: /continue to login/i }).click();
    await expect(page).toHaveURL(/\/login/);

    await attemptLogin(page, registration.email, registration.password);
    await page.waitForURL(/\/billing/);
  });
});

async function attemptLogin(page: Page, email: string, password: string) {
  const currentPath = new URL(page.url()).pathname;
  if (currentPath !== "/login") {
    await page.goto("/login");
  }
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password/i).fill(password);
  await page.getByRole("button", { name: /sign in/i }).click();
}

async function fetchLatestVerificationToken(
  request: APIRequestContext,
  email: string,
): Promise<string> {
  const response = await request.get(
    `/api/debug/latest-verification-token/?email=${encodeURIComponent(email)}`,
  );
  expect(response.ok()).toBeTruthy();
  const data = (await response.json()) as { token: string };
  return data.token;
}

async function expireVerificationToken(
  request: APIRequestContext,
  email: string,
) {
  const response = await request.post("/api/debug/expire-verification-token/", {
    data: { email },
  });
  expect(response.ok()).toBeTruthy();
}
