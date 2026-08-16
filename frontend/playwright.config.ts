import { defineConfig, devices } from "@playwright/test";
import dotenv from "dotenv";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const workspaceRoot = path.resolve(__dirname, "..");
const backendDir = path.join(workspaceRoot, "backend");
const e2eBackendPort = Number(process.env.PLAYWRIGHT_BACKEND_PORT ?? "18081");
const e2eFrontendPort = Number(process.env.PLAYWRIGHT_FRONTEND_PORT ?? "4173");
const externalBaseUrl = process.env.VITE_DEV_SERVER_URL;
const shouldManageWebServers = !externalBaseUrl;

const defaultBaseURL = (() => {
  const explicitBaseUrl = process.env.PLAYWRIGHT_BASE_URL;
  if (explicitBaseUrl) {
    return explicitBaseUrl;
  }

  if (externalBaseUrl) {
    return externalBaseUrl;
  }

  return `http://localhost:${e2eFrontendPort}`;
})();

const baseURL = defaultBaseURL;

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
  webServer: shouldManageWebServers
    ? [
        {
          command: `DJANGO_ENV=development API_RATE_LIMITING_ENABLED=0 python manage.py runserver 0.0.0.0:${e2eBackendPort}`,
          cwd: backendDir,
          port: e2eBackendPort,
          reuseExistingServer: false,
          timeout: 120_000,
        },
        {
          command: `VITE_SSL_CERT= VITE_SSL_KEY= VITE_PROXY_TARGET_PORT=${e2eBackendPort} npm run dev -- --host 0.0.0.0 --port ${e2eFrontendPort}`,
          cwd: __dirname,
          port: e2eFrontendPort,
          reuseExistingServer: false,
          timeout: 120_000,
        },
      ]
    : undefined,
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
