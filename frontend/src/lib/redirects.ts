export type AllowedRedirectPath =
  | "/dashboard"
  | "/billing"
  | "/billing/success"
  | "/billing/cancel";

export const allowedRedirectPaths: AllowedRedirectPath[] = [
  "/dashboard",
  "/billing",
  "/billing/success",
  "/billing/cancel",
];

const allowedRedirectPathSet = new Set(allowedRedirectPaths);

export const DEFAULT_REDIRECT: AllowedRedirectPath = "/dashboard";

export function sanitizeRedirectPath(
  value: unknown
): AllowedRedirectPath | null {
  if (typeof value !== "string") {
    return null;
  }

  if (!value.startsWith("/")) {
    return null;
  }

  if (!allowedRedirectPathSet.has(value as AllowedRedirectPath)) {
    return null;
  }

  return value as AllowedRedirectPath;
}
