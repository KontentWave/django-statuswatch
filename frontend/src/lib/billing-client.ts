import type { AxiosError } from "axios";

import { api } from "./api";

export type BillingPlan = "pro";

interface BillingCheckoutResponse {
  url?: string;
  detail?: string;
  error?: string;
}

export async function createBillingCheckoutSession(
  plan: BillingPlan
): Promise<string> {
  try {
    const { data } = await api.post<BillingCheckoutResponse>(
      "/billing/create-checkout-session/",
      { plan }
    );

    if (!data?.url) {
      throw new Error("Checkout session did not include a redirect URL.");
    }

    return data.url;
  } catch (error) {
    const axiosError = error as AxiosError<BillingCheckoutResponse>;
    const fallback =
      axiosError.message || "We could not start the Stripe checkout session.";

    throw new Error(
      axiosError.response?.data?.detail ||
        axiosError.response?.data?.error ||
        fallback
    );
  }
}
