import { defineConfig, devices } from "@playwright/test";

const PORT = 3200;

/**
 * Smoke tests run against a real production build with no Stripe or Blob
 * keys: orders go to a local folder (.data-test) and payment goes through the
 * fake checkout page.
 */
export default defineConfig({
  testDir: "tests/e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "retain-on-failure",
  },
  projects: [
    { name: "phone", use: { ...devices["Pixel 7"], viewport: { width: 375, height: 740 } } },
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
  ],
  webServer: {
    command: `rm -rf .data-test && npx next start -p ${PORT}`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      VELLUM_DATA_DIR: ".data-test",
      ADMIN_PASSWORD: "test-admin-password",
      ALLOW_FAKE_CHECKOUT: "1",
      CRON_SECRET: "test-cron-secret",
      STRIPE_SECRET_KEY: "",
      STRIPE_WEBHOOK_SECRET: "",
      BLOB_READ_WRITE_TOKEN: "",
      BLOB_STORE_ID: "",
    },
  },
});
