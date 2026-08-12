import { expect, test } from "@playwright/test";

const baseUrl = process.env.DOSCAN_TESTNET_URL;
const smokeName = process.env.DOS_NAMES_SMOKE_NAME;
const smokeAddress = process.env.DOS_NAMES_SMOKE_RESOLVED_ADDRESS;

if (!baseUrl || !smokeName || !smokeAddress) {
  throw new Error("Missing DOS Name smoke configuration");
}

test("DOS Name search resolves through the Testnet UI", async ({ page }) => {
  await page.goto(baseUrl, { waitUntil: "domcontentloaded" });

  const searchInput = page.locator('input[placeholder*="search" i]').first();
  await expect(searchInput).toBeVisible();

  const searchResponse = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v2/search") && response.status() === 200,
  );
  await searchInput.fill(smokeName);
  await searchResponse;

  const resultLink = page.locator("a").filter({ hasText: smokeName }).first();
  await expect(resultLink).toBeVisible();
  await expect(resultLink).toHaveAttribute(
    "href",
    new RegExp(`/address/${smokeAddress}$`, "i"),
  );

  await resultLink.click();
  await expect(page).toHaveURL(new RegExp(`/address/${smokeAddress}$`, "i"));
});
