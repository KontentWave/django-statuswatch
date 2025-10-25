export function redirectTo(url: string): void {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.location.assign(url);
  } catch {
    // Fallback when assign is not supported or throws in non-browser contexts.
    window.location.href = url;
  }
}
