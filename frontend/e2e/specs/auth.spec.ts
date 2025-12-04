import { test } from "@playwright/test";

import { AuthPage } from "../pages/auth-page";
import { buildRegistrationInput } from "../support/registration-data";

test.describe("Registration", () => {
  test("new visitor can provision an organization", async ({ page }) => {
    const authPage = new AuthPage(page);
    const registration = buildRegistrationInput();

    await test.step("Open the registration form", async () => {
      await authPage.gotoRegister();
    });

    await test.step("Submit valid registration details", async () => {
      await authPage.completeRegistration(registration);
    });

    await test.step("Verify redirect and success toast", async () => {
      await authPage.expectLoginRedirectWithSuccess();
    });
  });
});
