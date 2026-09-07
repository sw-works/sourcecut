/**
 * Demo-video stills, taken from the running app.
 *
 * Captured boards only: every frame is a real run that was captured and
 * committed, so the set needs the web app and nothing else — no API, no MCP
 * server, no ClickHouse. The video is cut from these rather than from a live
 * session, so the set has to carry every beat on its own: the plan, the trace,
 * the coverage rounds, the evidence, the rights, and the requirement the
 * corpus could not defend.
 *
 *   node docs/demo/shots.mjs [baseUrl]
 *
 * Needs `npm --prefix apps/web run build` and the built server running, and
 * playwright installed globally.
 */
import { chromium } from "/opt/homebrew/lib/node_modules/playwright/index.mjs";
import { mkdirSync } from "node:fs";

const BASE = process.argv[2] ?? "http://127.0.0.1:3000";
const OUT = "/Users/hanyu/dev/sourcecut/docs/demo/shots";

// The four boards the video walks, in the order it walks them.
const BOARDS = {
  bitterroot: "bitterroot-september-1805",
  greatFalls: "great-falls-portage-1805",
  lemhi: "lemhi-shoshone-august-1805",
  columbia: "columbia-descent-october-1805",
};

mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: { width: 1512, height: 950 },
  deviceScaleFactor: 2,
});
page.on("pageerror", (error) => console.error("PAGE ERROR", error.message));
page.on("response", (response) => {
  if (response.status() >= 400) console.error(`HTTP ${response.status()} ${response.url()}`);
});

const taken = [];
async function shot(name, options = {}) {
  await page.waitForTimeout(250);
  await page.screenshot({ path: `${OUT}/${name}.png`, ...options });
  taken.push(name);
  console.log(`  ${name}`);
}

/** A framed still of one element, rather than the whole window. */
async function shotOf(selector, name) {
  const target = page.locator(selector).first();
  if ((await target.count()) === 0) {
    console.log(`  (missing ${selector})`);
    return;
  }
  await target.scrollIntoViewIfNeeded();
  await page.waitForTimeout(250);
  const box = await target.boundingBox();
  if (!box) {
    console.log(`  (no box for ${selector})`);
    return;
  }
  await shot(name, { clip: box });
}

async function board(scope) {
  await page.goto(`${BASE}/board/${scope}`, { waitUntil: "networkidle" });
  await page.waitForSelector(".cut-survey");
}

/** Scroll one trace row into view, then frame the drawer around it. */
async function traceAt(eventType, name) {
  const row = page.locator(`.cut-trace li.${eventType}`).first();
  if ((await row.count()) === 0) {
    console.log(`  (no ${eventType} row on this board)`);
    return;
  }
  await row.scrollIntoViewIfNeeded();
  await shotOf(".cut-inspector.cut-trace", name);
}

// -- 01-05 · the shelf and the project dashboards ------------------------
console.log("landing");
await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
await shot("01-landing-hero");
await shot("02-landing-full", { fullPage: true });
await shotOf(".cut-corpus-grid", "03-corpus-cards");

console.log("project dashboards");
await page.goto(`${BASE}/project/lewis-and-clark`, { waitUntil: "networkidle" });
await page.waitForSelector(".cut-stage-strip");
await shot("04-project-journals");
const brief = page.locator("textarea").first();
if (await brief.count()) {
  await brief.fill(
    "The Great Falls portage, June and July 1805. I need the gear they carried and " +
      "built - the iron-frame boat, the carriage wheels and cords for the canoes - the " +
      "men doing the hauling, the ground between the falls, and the weather that hit them.",
  );
  await shot("05-brief-typed");
}

await page.goto(`${BASE}/project/odyssey`, { waitUntil: "networkidle" });
await page.waitForSelector(".cut-stage-strip");
await shot("06-project-odyssey");

// The switcher is the whole point of the two-project structure: open it.
await page.goto(`${BASE}/board/great-falls-portage-1805`, { waitUntil: "networkidle" });
await page.locator(".cut-switcher-button").click();
await page.waitForTimeout(400);
await shot("07-project-switcher");
await page.keyboard.press("Escape");
await page.waitForTimeout(300);

// -- 10-15 · the board, top to bottom --------------------------------------
console.log("board · great falls");
await board(BOARDS.greatFalls);
await shot("10-board-top");
await shot("11-board-full", { fullPage: true });
await shotOf(".cut-timeline", "12-evidence-timeline");

// Hold a day: the timeline, the matrices and the route all read one clock.
const nextDay = page.getByLabel("Next day");
if (await nextDay.count()) {
  for (let step = 0; step < 12; step += 1) await nextDay.click();
  await page.waitForTimeout(500);
  await shot("13-timeline-date-held");
}

await shotOf(".cut-survey", "14-survey-cards");
await shotOf(".cut-tabs", "15-requirement-tabs");

// -- 20-23 · one requirement, opened ---------------------------------------
console.log("requirement drill-down");
await page.locator(".cut-tab.met").first().click();
await page.waitForTimeout(400);
await page.locator(".cut-drill").scrollIntoViewIfNeeded();
await shot("20-requirement-open");
await shotOf(".cut-drill", "21-requirement-panel");
await shotOf(".cut-matrix", "22-agreement-matrix");

const quote = page.locator(".cut-quotes button").first();
if (await quote.count()) {
  await quote.click();
  // Wait for the passage to arrive rather than for a fixed interval: the
  // highlight only exists once the API has answered, and a cold first call can
  // take a couple of seconds.
  await page.waitForSelector(".cut-inspector mark", { timeout: 20_000 });
  // Bring the highlighted span into the frame: the quotation sits inside a
  // 4,000-character passage, and the highlight is the whole point of the shot.
  const highlight = page.locator(".cut-inspector mark").first();
  if (await highlight.count()) await highlight.scrollIntoViewIfNeeded();
  await shot("23-passage-inspector");
  // Frame the panel first, then scroll the highlight into view inside it:
  // scrollIntoViewIfNeeded on the panel moves the page and undoes the scroll
  // that put the highlighted span on screen.
  const panel = page.locator(".cut-inspector").first();
  const box = await panel.boundingBox();
  if (await highlight.count()) {
    await highlight.scrollIntoViewIfNeeded();
    await page.waitForTimeout(400);
  }
  if (box) await shot("24-passage-span", { clip: box });
  await page.locator(".cut-inspector .close").first().click();
}

// -- 30-31 · archive references and rights ---------------------------------
console.log("archive references");
const refs = page.locator(".cut-refs-block").first();
if (await refs.count()) {
  await shotOf(".cut-refs-block", "30-archive-references");
  await page.locator(".cut-ref").first().click();
  await page.waitForTimeout(500);
  await shot("31-reference-rights");
  await page.locator(".cut-inspector .close").first().click();
}

// -- 40-45 · the trace: plan, MCP calls, coverage rounds -------------------
console.log("execution trace");
await page.locator(".cut-trace-open").click();
await page.waitForTimeout(500);
await shot("40-trace-drawer");
await traceAt("plan_created", "41-trace-plan");
await traceAt("mcp_tool_call", "42-trace-mcp-calls");
await traceAt("gap_replan", "43-trace-gap-replan");
await traceAt("coverage_evaluated", "44-trace-coverage");
await shotOf(".cut-sql", "45-trace-sql");
await page.locator(".cut-inspector .close").first().click();

// -- 50 · the requirement the corpus could not defend ----------------------
console.log("the unmet requirement");
await shotOf(".cut-tabs", "50-unmet-requirement");

// -- 60-62 · a different brief plans different work ------------------------
console.log("four briefs, four plans");
for (const [name, scope] of [
  ["60-plan-bitterroot", BOARDS.bitterroot],
  ["61-plan-lemhi", BOARDS.lemhi],
  ["62-plan-columbia", BOARDS.columbia],
]) {
  await board(scope);
  await shotOf(".cut-tabs", name);
  await shot(`${name}-board`);
}

// -- 70-81 · the rail, and the phone ---------------------------------------
console.log("rail and phone");
await board(BOARDS.bitterroot);
await shotOf(".cut-rail", "70-board-rail");

const phone = await browser.newPage({
  viewport: { width: 390, height: 844 },
  deviceScaleFactor: 3,
});
await phone.goto(`${BASE}/board/${BOARDS.greatFalls}`, { waitUntil: "networkidle" });
await phone.screenshot({ path: `${OUT}/80-phone-board.png` });
taken.push("80-phone-board");
await phone.screenshot({ path: `${OUT}/81-phone-board-full.png`, fullPage: true });
taken.push("81-phone-board-full");

await browser.close();
console.log(`\n${taken.length} stills in ${OUT}`);
