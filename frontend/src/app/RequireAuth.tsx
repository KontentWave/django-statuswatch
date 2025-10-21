import type { PropsWithChildren, ReactElement } from "react";

/**
 * Legacy wrapper retained for compatibility with older components.
 * Route-level guards now handle authentication redirects, so this
 * component simply renders its children.
 */
export function RequireAuth({ children }: PropsWithChildren): ReactElement {
  return <>{children}</>;
}
