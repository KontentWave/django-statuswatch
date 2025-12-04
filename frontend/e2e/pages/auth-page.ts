import { expect, Page } from "@playwright/test";

export type RegistrationFormInput = {
  organizationName: string;
  email: string;
  password: string;
};

export class AuthPage {
  constructor(private readonly page: Page) {}

  async gotoRegister(): Promise<void> {
    await this.page.goto("/register");
    await expect(
      this.page.getByRole("heading", { name: /create your organization/i })
    ).toBeVisible();
  }

  async completeRegistration(formInput: RegistrationFormInput): Promise<void> {
    await this.page
      .getByLabel("Organization Name")
      .fill(formInput.organizationName);
    await this.page.getByLabel("Email", { exact: true }).fill(formInput.email);
    await this.page
      .getByLabel("Password", { exact: true })
      .fill(formInput.password);
    await this.page
      .getByLabel("Confirm Password", { exact: true })
      .fill(formInput.password);

    const submit = this.page.getByRole("button", { name: /sign up/i });
    await Promise.all([this.page.waitForURL(/\/login$/), submit.click()]);
  }

  async expectLoginRedirectWithSuccess(
    messageSubstring = "Registration successful"
  ): Promise<void> {
    await expect(this.page).toHaveURL(/\/login$/);
    const successBanner = this.page.getByText(messageSubstring, {
      exact: false,
    });
    await expect(successBanner).toBeVisible();
    await expect(
      this.page.getByRole("heading", { name: /sign in to statuswatch/i })
    ).toBeVisible();
  }
}
