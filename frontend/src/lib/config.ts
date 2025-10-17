export const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined) ??
  'https://statuswatch.local/api';

export const STRIPE_PK =
  (import.meta.env.VITE_STRIPE_PUBLIC_KEY as string | undefined) ?? '';
