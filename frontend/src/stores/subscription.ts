import { create } from "zustand";

import { logSubscriptionEvent } from "@/lib/subscription-logger";
import type { SubscriptionPlan } from "@/types/api";

interface SubscriptionState {
  plan: SubscriptionPlan;
  setPlan: (plan: SubscriptionPlan) => void;
  reset: () => void;
}

const initialState: Pick<SubscriptionState, "plan"> = {
  plan: "free",
};

export const useSubscriptionStore = create<SubscriptionState>((set) => ({
  ...initialState,
  setPlan: (plan) =>
    set((state) => {
      if (state.plan !== plan) {
        void logSubscriptionEvent({
          event: "plan_change",
          action: "state_change",
          previousPlan: state.plan,
          nextPlan: plan,
        });
      }
      return { plan };
    }),
  reset: () =>
    set((state) => {
      if (state.plan !== initialState.plan) {
        void logSubscriptionEvent({
          event: "plan_change",
          action: "state_change",
          previousPlan: state.plan,
          nextPlan: initialState.plan,
          reason: "reset",
        });
      }
      return initialState;
    }),
}));

export const resetSubscriptionStore = () =>
  useSubscriptionStore.getState().reset();

export type { SubscriptionPlan };
