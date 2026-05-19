import { test, expect } from "@playwright/test";

test.skip(!!process.env.E2E_SKIP_SMOKE, "E2E_SKIP_SMOKE set");

test("calculator: SIP returns Calculated + Projected numbers", async ({ page }) => {
  await page.goto("/calculator");

  // Pick a fund via the search input that's embedded in the page.
  const search = page.getByRole("textbox").first();
  await search.fill("HDFC");
  await page.locator("text=HDFC").first().click();

  // Default amount + tenure are pre-filled. Submit.
  const calcButton = page.getByRole("button", { name: /calculate|project/i }).first();
  await calcButton.click();

  await expect(page.locator("text=Calculated return")).toBeVisible({ timeout: 20_000 });
  await expect(page.locator("text=Projected return")).toBeVisible();
});
