import crypto from "node:crypto";

import type { RegistrationFormInput } from "../pages/auth-page";

function uniqueSuffix(): string {
  return crypto.randomUUID().replace(/-/g, "").slice(0, 12);
}

export function buildRegistrationInput(): RegistrationFormInput {
  const suffix = uniqueSuffix();
  return {
    organizationName: `Playwright Org ${suffix}`,
    email: `playwright+${suffix}@example.com`,
    password: `Sup3rSecure!${suffix}Aa1`,
  };
}
