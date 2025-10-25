const LAST_CHECKOUT_PLAN_KEY = "statuswatch:lastCheckoutPlan";

export function rememberCheckoutPlan(plan: string): void {
  if (typeof window === "undefined") {
    return;
  }

  window.sessionStorage.setItem(LAST_CHECKOUT_PLAN_KEY, plan);
}

export function clearCheckoutPlan(): void {
  if (typeof window === "undefined") {
    return;
  }

  window.sessionStorage.removeItem(LAST_CHECKOUT_PLAN_KEY);
}

export function consumeCheckoutPlan(): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  const plan = window.sessionStorage.getItem(LAST_CHECKOUT_PLAN_KEY);
  if (plan !== null) {
    window.sessionStorage.removeItem(LAST_CHECKOUT_PLAN_KEY);
  }
  return plan;
}
