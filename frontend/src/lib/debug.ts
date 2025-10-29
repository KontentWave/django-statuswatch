// frontend/src/lib/debug.ts
/**
 * Debug logging utilities for development environment.
 *
 * In production builds (npm run build), these will be no-ops
 * as import.meta.env.DEV is false.
 */

export const isDev = import.meta.env.DEV;

/**
 * Log debug messages only in development mode.
 * In production, this is a no-op.
 */
export const debug = (...args: unknown[]) => {
  if (isDev) console.log(...args);
};

/**
 * Log error messages only in development mode.
 * In production, this is a no-op.
 *
 * For production error tracking, use Sentry or send to backend.
 */
export const debugError = (...args: unknown[]) => {
  if (isDev) console.error(...args);
};

/**
 * Log warning messages only in development mode.
 * In production, this is a no-op.
 */
export const debugWarn = (...args: unknown[]) => {
  if (isDev) console.warn(...args);
};
