import { expect, test } from "@playwright/test";

const baseUrl = process.env.DOSCAN_MAINNET_URL;
const entryPointAddress = "0x0000000071727De22E5E9d8BAf0edAc6f37da032";

if (!baseUrl) {
  throw new Error("Missing DOSCAN_MAINNET_URL");
}

const targets = [
  {
    address: entryPointAddress,
    name: "EntryPoint",
    compiler: "v0.8.23+commit.f704f362",
    sourcePath: "contracts/core/EntryPoint.sol",
    optimizerRuns: 1_000_000,
    evmVersion: "paris",
    license: "gnu_gpl_v3",
    constructorArgs: "",
  },
  {
    address: "0xd6CEDDe84be40893d153Be9d467CD6aD37875b28",
    name: "Kernel",
    compiler: "v0.8.28+commit.7893614a",
    sourcePath: "src/Kernel.sol",
    optimizerRuns: 200,
    evmVersion: "prague",
    license: "mit",
    constructorArgs: "0000000000000000000000000000000071727de22e5e9d8baf0edac6f37da032",
  },
  {
    address: "0x2577507b78c2008Ff367261CB6285d44ba5eF2E9",
    name: "KernelFactory",
    compiler: "v0.8.28+commit.7893614a",
    sourcePath: "dependencies/kernel-v3.3/src/factory/KernelFactory.sol",
    optimizerRuns: 200,
    evmVersion: "prague",
    license: "mit",
    constructorArgs: "000000000000000000000000d6cedde84be40893d153be9d467cd6ad37875b28",
  },
  {
    address: "0x845ADb2C711129d4f3966735eD98a9F09fC4cE57",
    name: "ECDSAValidator",
    compiler: "v0.8.25+commit.b61c2a91",
    sourcePath: "src/validator/ECDSAValidator.sol",
    optimizerRuns: 200,
    evmVersion: "paris",
    license: "mit",
    constructorArgs: "",
  },
  {
    address: "0xd703aaE79538628d27099B8c4f621bE4CCd142d5",
    name: "FactoryStaker",
    compiler: "v0.8.24+commit.e11b9ed9",
    sourcePath: "src/factory/FactoryStaker.sol",
    optimizerRuns: 200,
    evmVersion: "paris",
    license: "mit",
    constructorArgs: "",
  },
];

function normalizeCompiler(value) {
  return value.startsWith("v") ? value : `v${value}`;
}

function normalizeHex(value) {
  return (value || "").toLowerCase().replace(/^0x/, "");
}

async function skipOnlyCloudflareChallenge(page) {
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
}

async function openExplorer(page) {
  await page.setViewportSize({ width: 1440, height: 900 });
  for (let attempt = 1; attempt <= 6; attempt += 1) {
    let response;
    try {
      response = await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
    } catch {
      response = null;
    }
    await skipOnlyCloudflareChallenge(page);
    const visibleContent = page.locator("main:visible, body:visible").first();
    if (response?.ok() && (await visibleContent.isVisible())) {
      return;
    }
    if (attempt < 6) {
      await page.waitForTimeout(5_000);
    }
  }
  throw new Error(`Mainnet explorer did not become ready: ${page.url()}`);
}

function expectExactMetadata(metadata, target) {
  expect(metadata.is_verified).toBe(true);
  expect(metadata.is_fully_verified).toBe(true);
  expect(metadata.is_partially_verified).toBe(false);
  expect(metadata.verified_twin_address_hash).toBeNull();
  expect(metadata.name).toBe(target.name);
  expect(normalizeCompiler(metadata.compiler_version)).toBe(target.compiler);
  expect(metadata.file_path).toBe(target.sourcePath);
  expect(metadata.optimization_enabled).toBe(true);
  expect(metadata.optimization_runs).toBe(target.optimizerRuns);
  expect(metadata.evm_version).toBe(target.evmVersion);
  expect(metadata.license_type).toBe(target.license);
  expect(normalizeHex(metadata.constructor_args)).toBe(normalizeHex(target.constructorArgs));
}

test("five Mainnet DOS ID Wallet contracts are exactly verified", async ({ page, request }) => {
  test.setTimeout(180_000);
  await openExplorer(page);

  for (const target of targets) {
    const apiUrl = new URL(`/api/v2/smart-contracts/${target.address}`, baseUrl);
    const apiResponse = await request.get(apiUrl.toString());
    expect(apiResponse.ok()).toBe(true);
    expectExactMetadata(await apiResponse.json(), target);

    const contractUrl = new URL(`/address/${target.address}?tab=contract`, baseUrl);
    const response = await page.goto(contractUrl.toString(), { waitUntil: "domcontentloaded" });
    expect(response?.ok()).toBe(true);
    await skipOnlyCloudflareChallenge(page);
    await expect(page.getByText(target.name, { exact: true }).first()).toBeVisible({ timeout: 30_000 });
    await expect(
      page.getByText(/Contract source code verified|Fully verified|Exact match/i).first(),
    ).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText("Oops! Something went wrong")).toHaveCount(0);
  }
});

test("Mainnet operations page exposes EntryPoint v0.7 activity", async ({ page, request }) => {
  test.setTimeout(90_000);
  await openExplorer(page);

  const operationsApi = new URL("/api/v2/proxy/account-abstraction/operations", baseUrl);
  const apiResponse = await request.get(operationsApi.toString());
  expect(apiResponse.ok()).toBe(true);
  const payload = await apiResponse.json();
  expect(Array.isArray(payload.items)).toBe(true);
  expect(payload.items.length).toBeGreaterThan(0);
  expect(
    payload.items.some(
      (item) =>
        (
          item.entry_point?.hash ||
          item.entry_point_address ||
          item.entry_point ||
          ""
        ).toLowerCase() === entryPointAddress.toLowerCase(),
    ),
  ).toBe(true);

  const opsUrl = new URL("/ops", baseUrl);
  const response = await page.goto(opsUrl.toString(), { waitUntil: "domcontentloaded" });
  expect(response?.ok()).toBe(true);
  await skipOnlyCloudflareChallenge(page);
  await expect(page.locator('tbody tr:visible, [role="row"]:visible').nth(1)).toBeVisible({ timeout: 30_000 });
  const shortEntryPoint = `${entryPointAddress.slice(0, 8)}...${entryPointAddress.slice(-4)}`;
  await expect(page.getByText(new RegExp(`${entryPointAddress}|${shortEntryPoint}`, "i")).first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Oops! Something went wrong")).toHaveCount(0);
});
