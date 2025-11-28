// Centralized API-facing types shared across monitoring and billing surfaces.
// Re-exporting from client modules keeps React components/tests decoupled
// from implementation details inside lib/ while guaranteeing parity with
// backend DTO contracts.

export type SubscriptionPlan = "free" | "pro" | "canceled";

export interface CurrentUserResponse {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  is_staff: boolean;
  date_joined: string;
  groups: string[];
  plan: SubscriptionPlan;
}

export type {
  EndpointDto,
  EndpointListResponse,
  EndpointListParams,
  CreateEndpointRequest,
  DeleteEndpointResult,
} from "@/lib/endpoint-client";

export type {
  BillingPlan,
  BillingCheckoutResponse,
  BillingPortalResponse,
  BillingCancelResponse,
} from "@/lib/billing-client";

export type { BillingLogEntry } from "@/lib/billing-logger";
