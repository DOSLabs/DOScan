import { expect, test } from "@playwright/test";

const baseUrl = process.env.DOSCAN_TESTNET_URL;
const smokeName = process.env.DOS_NAMES_SMOKE_NAME;
const smokeAddress = process.env.DOS_NAMES_SMOKE_RESOLVED_ADDRESS;

if (!baseUrl || !smokeName || !smokeAddress) {
  throw new Error("Missing DOS Name smoke configuration");
}

test("DOS Name search resolves through the Testnet UI", async ({ page }) => {
  test.setTimeout(90_000);
  await page.goto(baseUrl, { waitUntil: "domcontentloaded" });

  const searchInput = page
    .locator('input[placeholder*="search" i]:visible')
    .first();
  await expect(searchInput).toBeVisible({ timeout: 30_000 });

  const searchResponse = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v2/search") && response.status() === 200,
  );
  await searchInput.fill(smokeName);
  await searchResponse;

  const resultLink = page.locator("a").filter({ hasText: smokeName }).first();
  await expect(resultLink).toBeVisible({ timeout: 30_000 });
  await expect(resultLink).toHaveAttribute(
    "href",
    new RegExp(`/address/${smokeAddress}$`, "i"),
  );

  await resultLink.click();
  await expect(page).toHaveURL(new RegExp(`/address/${smokeAddress}$`, "i"));

  const domainDetailsUrl = new URL(
    `/name-services/domains/${smokeName}`,
    baseUrl,
  );
  await page.goto(domainDetailsUrl.toString(), { waitUntil: "domcontentloaded" });
  await expect(
    page.getByText(smokeAddress, { exact: false }).first(),
  ).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(smokeName, { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Oops! Something went wrong")).toHaveCount(0);
});
