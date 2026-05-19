import { defineConfig, devices } from "@playwright/test";

/**
 * Z1N MF Analyser - end-to-end Playwright config.
 *
 * Assumes the dev stack is already running on http://localhost:5173
 * (frontend) + http://localhost:8000 (backend). Bring it up with:
 *   docker compose up -d
 * before running `npm test`.
 */
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,                    // Backend has shared state.
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  timeout: 60 * 1000,
  expect: { timeout: 10 * 1000 },
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:5173",
    actionTimeout: 10 * 1000,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
});
