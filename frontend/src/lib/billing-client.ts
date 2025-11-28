import type { AxiosError } from "axios";

import { api } from "./api";

export type BillingPlan = "pro";

export interface BillingCheckoutResponse {
  url?: string;
  detail?: string;
  error?: string;
}

export interface BillingPortalResponse {
  url?: string;
  detail?: string;
  error?: string;
}

export interface BillingCancelResponse {
  plan?: string;
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
    const fallback = "We could not start the Stripe checkout session.";

    throw new Error(
      axiosError.response?.data?.detail ||
        axiosError.response?.data?.error ||
        fallback
    );
  }
}

export async function createBillingPortalSession(): Promise<string> {
  try {
    const { data } = await api.post<BillingPortalResponse>(
      "/billing/create-portal-session/"
    );

    if (!data?.url) {
      throw new Error("Portal session did not include a redirect URL.");
    }

    return data.url;
  } catch (error) {
    const axiosError = error as AxiosError<BillingPortalResponse>;
    const fallback =
      axiosError.message ||
      "We could not open the Stripe billing portal. Please try again.";

    throw new Error(
      axiosError.response?.data?.detail ||
        axiosError.response?.data?.error ||
        fallback
    );
  }
}

export async function cancelBillingSubscription(): Promise<string> {
  try {
    const { data } = await api.post<BillingCancelResponse>("/billing/cancel/");

    if (!data?.plan) {
      throw new Error("Cancellation response did not include the new plan.");
    }

    return data.plan;
  } catch (error) {
    const axiosError = error as AxiosError<BillingCancelResponse>;
    const fallback =
      axiosError.message ||
      "We could not cancel your subscription. Please try again or contact support.";

    throw new Error(
      axiosError.response?.data?.detail ||
        axiosError.response?.data?.error ||
        fallback
    );
  }
}
