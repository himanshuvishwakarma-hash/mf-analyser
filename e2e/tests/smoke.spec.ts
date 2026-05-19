/**
 * Smoke test: app loads, search returns results, fund detail renders.
 * Skip with E2E_SKIP_SMOKE=1 if the stack isn't seeded yet.
 */
import { test, expect } from "@playwright/test";

test.skip(!!process.env.E2E_SKIP_SMOKE, "E2E_SKIP_SMOKE set");

test("app loads and search returns results", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/search/);

  const input = page.getByRole("textbox").first();
  await input.fill("HDFC");
  // Wait for at least one fund card / row to appear.
  await expect(page.locator("text=HDFC").first()).toBeVisible({ timeout: 15_000 });
});

test("open fund detail page", async ({ page }) => {
  await page.goto("/search");
  await page.getByRole("textbox").first().fill("HDFC");
  await page.locator("text=HDFC").first().click();
  // Returns or NAV section should appear on detail.
  await expect(page.locator("text=Returns")).toBeVisible({ timeout: 15_000 });
});
