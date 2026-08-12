import { expect, test } from "@playwright/test";

const baseUrl = process.env.DOSCAN_MAINNET_URL;
const smokeName = process.env.DOS_NAMES_SMOKE_NAME;
const smokeAddress = process.env.DOS_NAMES_SMOKE_RESOLVED_ADDRESS;

if (!baseUrl || !smokeName || !smokeAddress) {
  throw new Error("Missing DOS Name smoke configuration");
}

async function openExplorerWithSearch(page) {
  await page.setViewportSize({ width: 1440, height: 900 });

  for (let attempt = 1; attempt <= 6; attempt += 1) {
    let response;
    try {
      response = await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
    } catch {
      response = null;
    }

    const title = await page.title();
    if (
      title === "Just a moment..." &&
      page.url().includes("__cf_chl_rt_tk=")
    ) {
      test.skip(
        true,
        "Cloudflare challenged the GitHub runner; deployment API gates remain authoritative",
      );
    }

    const searchInput = page
      .locator('input[placeholder*="search" i]:visible')
      .first();
    if (response?.ok() && (await searchInput.isVisible())) {
      return searchInput;
    }

    if (attempt < 6) {
      await page.waitForTimeout(5_000);
    }
  }

  throw new Error(
    `Explorer search did not become visible: url=${page.url()} title=${await page.title()}`,
  );
}

test("DOS Name search resolves through the Mainnet UI", async ({ page }) => {
  test.setTimeout(90_000);
  const searchInput = await openExplorerWithSearch(page);
  await expect(searchInput).toBeVisible({ timeout: 30_000 });

  const searchResponse = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v2/search") && response.status() === 200,
  );
  await searchInput.fill(smokeName);
  await searchResponse;

  const resultLink = page
    .locator("a:visible")
    .filter({ hasText: smokeName })
    .first();
  await expect(resultLink).toBeVisible({ timeout: 30_000 });
  await expect(resultLink).toHaveAttribute(
    "href",
    new RegExp(`/address/${smokeAddress}$`, "i"),
  );

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
