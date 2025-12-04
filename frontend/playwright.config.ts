import { defineConfig, devices } from "@playwright/test";
import dotenv from "dotenv";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const defaultBaseURL = (() => {
  if (process.env.VITE_DEV_SERVER_URL) {
    return process.env.VITE_DEV_SERVER_URL;
  }

  const certPath = process.env.VITE_SSL_CERT;
  const keyPath = process.env.VITE_SSL_KEY;
  if (
    certPath &&
    keyPath &&
    fs.existsSync(certPath) &&
    fs.existsSync(keyPath)
  ) {
    return "https://localhost:5173";
  }

  return "http://localhost:5173";
})();

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? defaultBaseURL;

export default defineConfig({
  testDir: path.join(__dirname, "e2e", "specs"),
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 3 : undefined,
  reporter: process.env.CI
    ? [
        ["github"],
        ["html", { outputFolder: "playwright-report", open: "never" }],
      ]
    : "list",
  timeout: 90_000,
  expect: { timeout: 10_000 },
  globalSetup: path.join(__dirname, "e2e", "global-setup.ts"),
  use: {
    baseURL,
    ignoreHTTPSErrors: true, // self-signed dev certs
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "firefox",
      use: { ...devices["Desktop Firefox"] },
    },
    {
      name: "webkit",
      use: { ...devices["Desktop Safari"] },
    },
  ],
});
