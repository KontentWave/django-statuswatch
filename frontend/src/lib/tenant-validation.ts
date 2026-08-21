export function shouldSkipTenantValidation(
  pathname: string,
  hash: string,
): boolean {
  return pathname === "/login" && hash.includes("session=");
}
