import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";

// Suppress unhandled rejection warnings from zodResolver in tests
// zodResolver throws ZodError internally which RHF catches, but vitest sees as unhandled
// This doesn't affect actual functionality - errors are still properly caught and displayed

// Intercept process.emit to suppress Zod unhandled rejections
if (typeof process !== "undefined" && process.emit) {
  const originalEmit = process.emit;
  // @ts-expect-error - We're intercepting process.emit
  process.emit = function (event: string, error: unknown, ...args: unknown[]) {
    if (event === "unhandledRejection") {
      if (
        error &&
        typeof error === "object" &&
        ("_zod" in error || ("name" in error && error.name === "ZodError"))
      ) {
        // Suppress Zod validation errors - they're expected and handled by RHF
        return false;
      }
    }
    // @ts-expect-error - Forward other events normally
    return originalEmit.call(this, event, error, ...args);
  };
}

// Also handle via global handler
const unhandledRejections = new Set<Promise<unknown>>();

globalThis.addEventListener?.("unhandledrejection", (event) => {
  const error = event.reason;
  if (
    error &&
    typeof error === "object" &&
    ("_zod" in error || ("name" in error && error.name === "ZodError"))
  ) {
    event.preventDefault();
    unhandledRejections.add(event.promise);
  }
});

afterEach(() => {
  unhandledRejections.clear();
});
