import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Mocked } from "vitest";
import type { AxiosError } from "axios";

import { createBillingCheckoutSession } from "../billing-client";
import type { BillingCheckoutResponse } from "@/types/api";

vi.mock("../api", () => ({
  api: {
    post: vi.fn(),
  },
}));

type ApiDouble = typeof import("../api")["api"];

describe("billing-client", () => {
  let apiMock: Mocked<ApiDouble>;

  beforeEach(async () => {
    const module = await import("../api");
    apiMock = vi.mocked(module.api);
    apiMock.post.mockReset();
  });

  it("returns the Stripe checkout URL when the response contains one", async () => {
    const redirectUrl = "https://stripe.test/session/123";
    apiMock.post.mockResolvedValue({ data: { url: redirectUrl } });

    await expect(createBillingCheckoutSession("pro")).resolves.toBe(
      redirectUrl
    );
    expect(apiMock.post).toHaveBeenCalledWith(
      "/billing/create-checkout-session/",
      { plan: "pro" }
    );
  });

  it("surfaces backend detail messages for checkout failures", async () => {
    const axiosError = {
      message: "Stripe refused the request",
      response: { data: { detail: "Stripe temporarily unavailable" } },
    } as AxiosError<BillingCheckoutResponse>;
    apiMock.post.mockRejectedValue(axiosError);

    await expect(createBillingCheckoutSession("pro")).rejects.toThrow(
      "Stripe temporarily unavailable"
    );
  });

  it("falls back to the generic helper message when detail/error fields are missing", async () => {
    const axiosError = {
      message: "gateway timeout",
    } as AxiosError<BillingCheckoutResponse>;
    apiMock.post.mockRejectedValue(axiosError);

    await expect(createBillingCheckoutSession("pro")).rejects.toThrow(
      "We could not start the Stripe checkout session."
    );
  });
});
