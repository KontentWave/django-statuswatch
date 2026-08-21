import { describe, expect, it } from "vitest";

import { shouldSkipTenantValidation } from "@/lib/tenant-validation";

describe("shouldSkipTenantValidation", () => {
  it("skips validation for login session transfer handoff", () => {
    expect(
      shouldSkipTenantValidation("/login", "#session=abc&source=homepage_demo"),
    ).toBe(true);
  });

  it("does not skip validation for normal tenant login", () => {
    expect(shouldSkipTenantValidation("/login", "")).toBe(false);
  });

  it("does not skip validation for other tenant routes", () => {
    expect(shouldSkipTenantValidation("/dashboard", "#session=abc")).toBe(
      false,
    );
  });
});
