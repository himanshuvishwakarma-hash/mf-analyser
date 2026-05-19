import { test, expect } from "@playwright/test";

test.skip(!!process.env.E2E_SKIP_SMOKE, "E2E_SKIP_SMOKE set");

test("export factsheet from fund detail (Word)", async ({ page }) => {
  await page.goto("/search");
  await page.getByRole("textbox").first().fill("HDFC");
  await page.locator("text=HDFC").first().click();

  // Open the Export dropdown and pick Word.
  await page.getByRole("button", { name: /export/i }).click();
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: /word/i }).click(),
  ]);

  const path = await download.path();
  expect(path).toBeTruthy();
  expect(download.suggestedFilename()).toMatch(/factsheet_.*\.docx$/);
});
