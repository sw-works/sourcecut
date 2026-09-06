/**
 * Demo-video stills, taken from the running app rather than mocked up.
 *
 * A live session is the point of several of these, so the script drives the
 * real brief through the real API: it navigates to /board/live?q=..., grabs the
 * in-progress trace while the run is still working, and waits for the board to
 * replace it. Nothing here fabricates a state the app cannot reach.
 *
 *   node docs/demo/shots.mjs [baseUrl]
 *
 * Needs the API (python -m sourcecut_api.main) and the web app on 4321, and
 * playwright installed globally.
 */
import { chromium } from "/opt/homebrew/lib/node_modules/playwright/index.mjs";
import { mkdirSync } from "node:fs";

const BASE = process.argv[2] ?? "http://127.0.0.1:4321";
const OUT = "/Users/hanyu/dev/sourcecut/docs/demo/shots";
const BRIEF =
  "The Great Falls portage, June and July 1805. I need the gear they carried and " +
  "built - the iron-frame boat, the carriage wheels and cords for the canoes - the " +
  "men doing the hauling, the ground between the falls, and the weather that hit them.";

mkdirSync(OUT, { recursive: true });

const shots = [];
async function shot(page, name, options = {}) {
  const path = `${OUT}/${name}.png`;
  await page.screenshot({ path, ...options });
  shots.push(name);
  console.log(`  ${name}`);
}

const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: { width: 1512, height: 950 },
  deviceScaleFactor: 2,
});
page.on("pageerror", (error) => console.error("PAGE ERROR", error.message));

console.log("landing");
await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
await shot(page, "01-landing-hero");
await shot(page, "02-landing-full", { fullPage: true });

console.log("captured board");
await page.goto(`${BASE}/board/great-falls-portage-1805`, { waitUntil: "networkidle" });
await shot(page, "03-board-top");
await shot(page, "04-board-full", { fullPage: true });

// The requirement the corpus could not defend is a disabled tab: it is a
// result, not an error, and the demo shows it sitting in the row.
const tabs = page.locator(".cut-tabs");
if (await tabs.count()) {
  await tabs.scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  await shot(page, "05-requirement-tabs");
}

const met = page.locator(".cut-tab.met").first();
if (await met.count()) {
  await met.click();
  await page.waitForTimeout(400);
  await page.locator(".cut-drill").scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  await shot(page, "06-requirement-evidence");
}

await page.locator(".cut-trace-open").click();
await page.waitForTimeout(500);
await shot(page, "07-trace-drawer");
await page.keyboard.press("Escape").catch(() => {});
await page.locator(".cut-inspector .close").click();

console.log("live session");
await page.goto(`${BASE}/board/live?q=${encodeURIComponent(BRIEF)}`);
// Catch the run in progress. Events do not arrive one per second — the stream
// delivers them in bursts as stages finish — so this samples on a clock rather
// than waiting for a step count that may never be observed mid-flight.
await page.waitForSelector(".cut-progress", { timeout: 60_000 });
for (let frame = 1; frame <= 14; frame += 1) {
  if ((await page.locator(".cut-progress").count()) === 0) break;
  const steps = await page.locator(".cut-progress ol li").count();
  await shot(page, `08-live-${String(frame).padStart(2, "0")}-${steps - 1}-steps`);
  await page.waitForTimeout(4_000);
}

console.log("live board");
await page.waitForSelector(".cut-survey", { timeout: 300_000 });
await page.waitForTimeout(1200);
await shot(page, "11-live-complete");
await shot(page, "12-live-complete-full", { fullPage: true });

console.log("phone");
const phone = await browser.newPage({
  viewport: { width: 390, height: 844 },
  deviceScaleFactor: 3,
});
await phone.goto(`${BASE}/board/great-falls-portage-1805`, { waitUntil: "networkidle" });
await phone.screenshot({ path: `${OUT}/13-phone-board.png` });
shots.push("13-phone-board");

await browser.close();
console.log(`\n${shots.length} stills in ${OUT}`);
