import { diagram, node } from "./svg.mjs";
// 01 — where every part runs and which path reaches ClickHouse (apps/web, apps/api,
// integrations/clickhouse_mcp.py, sql/security/odyssey_mcp_role.sql). Drawn from the code
// as built. Two access paths, deliberately: read-only MCP at runtime, direct admin for writes.
export default () => diagram({
  width: 1560, height: 700,
  title: "01 · System topology",
  subtitle: "Runtime research reaches ClickHouse only through the read-only MCP server. Every write goes down the separate admin path.",
  groups: [
    { x: 24, y: 84, w: 320, h: 300, label: "browser" },
    { x: 368, y: 84, w: 700, h: 480, label: "cloud run" },
    { x: 1092, y: 84, w: 444, h: 480, label: "managed services" },
  ],
  nodes: [
    node("static", 48, 120, 272, 60, "prerendered Astro", { kind: "det", sub: "landing · corpus · 24 book routes" }),
    node("islands", 48, 200, 272, 60, "React islands", { kind: "det", sub: "board · timeline · claims" }),
    node("gateway", 48, 290, 272, 60, "same-origin gateway", { kind: "det", sub: "pages/sourcecut-api/[...path]" }),

    node("api", 392, 120, 300, 60, "FastAPI", { kind: "det", sub: "70 routes, two corpora · SSE timeline" }),
    node("board", 392, 210, 300, 60, "ResearchBoardService", { kind: "det", sub: "plan · retrieve · score coverage\nruns on a worker loop" }),
    node("planner", 392, 300, 300, 56, "planner", { kind: "det", sub: "Gemini or keyword routing" }),
    node("mcpclient", 392, 476, 300, 56, "ClickHouseMcpClient", { kind: "det", sub: "run_query guardrail" }),

    node("adk", 740, 120, 300, 60, "ADK research CLI", { kind: "llm", sub: "single agent or --pipeline" }),
    node("admin", 740, 476, 300, 56, "clickhouse-connect", { kind: "det", sub: "ingestion · migrations · sessions" }),

    node("gemini", 1116, 120, 396, 60, "Gemini", { kind: "ext", sub: "planning · extraction · visual inspection" }),
    node("mcp", 1116, 300, 396, 60, "mcp-clickhouse", { kind: "ext", sub: "official server · read-only role" }),
    node("ch", 1116, 440, 396, 90, "ClickHouse Cloud", {
      kind: "ext",
      sub: "evidence · reference data · sessions and events\n133 migrations · row policies · parametrized views",
    }),
  ],
  edges: [
    { from: "islands", to: "gateway", muted: true },
    { from: "gateway", to: "api", label: "same origin", at: [356, 240] },
    { from: "api", to: "board" },
    { from: "board", to: "planner" },
    { from: "planner", to: "mcpclient", points: [[542, 356], [542, 474]] },
    { from: "planner", to: "gemini", points: [[694, 328], [880, 328], [880, 200], [1300, 200], [1300, 182]], label: "typed plan request", at: [1000, 200] },
    { from: "adk", to: "mcp", points: [[1042, 150], [1080, 150], [1080, 330], [1114, 330]], label: "ADK toolset", at: [1080, 246] },
    {
      from: "mcpclient", to: "mcp",
      points: [[542, 534], [542, 548], [1096, 548], [1096, 345], [1114, 345]],
      label: "list_tables · run_query", at: [820, 548],
    },
    { from: "mcp", to: "ch", label: "read-only", at: [1420, 400] },
    { from: "admin", to: "ch", muted: true, points: [[1042, 504], [1080, 504], [1080, 470], [1114, 470]], label: "writes", at: [1046, 456] },
    { from: "board", to: "admin", muted: true, points: [[692, 240], [730, 240], [730, 504], [738, 504]], label: "sessions,\nevents,\nvocabulary", at: [772, 380] },
  ],
  legend: ["det", "llm", "ext"],
  notes: [
    "Prerendered routes never touch ClickHouse or MCP, so ordinary page delivery does not depend on either being up (ADR-018).",
    "The ADK CLI and the product path use the same MCP server and the same guardrail; only the CLI runs a model tool loop.",
    "Drawn 2026-09-06 from feat/ui-redesign; route and migration counts checked against the running app.",
  ],
});
