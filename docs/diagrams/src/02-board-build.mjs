import { diagram, node } from "./svg.mjs";
// 02 — the board build as built (services/board.py::build_board). Every branch, every
// emitted event, and the three retrieval paths that can produce evidence. Reference
// drawing, not a slide.
export default () => diagram({
  width: 1660, height: 800,
  title: "02 · Board build, end to end",
  subtitle: "POST /api/research to a persisted board. Timeline events are written as the run proceeds, so the SSE stream replays real state rather than a script.",
  groups: [
    { x: 24, y: 84, w: 500, h: 400, label: "plan" },
    { x: 548, y: 84, w: 560, h: 400, label: "retrieve and score" },
    { x: 1132, y: 84, w: 504, h: 400, label: "verify and assemble" },
  ],
  nodes: [
    node("post", 48, 130, 200, 56, "POST /api/research", { kind: "ext" }),
    node("session", 48, 216, 200, 56, "session created", { kind: "det", sub: "202 + events_url" }),
    node("plan", 288, 130, 212, 70, "planner.plan", { kind: "llm", sub: "scope_id, requirements" }),
    node("built", 288, 232, 212, 60, "ResearchPlan", { kind: "state", sub: "window from file" }),
    node("static", 288, 340, 212, 56, "StaticResearchPlanner", { kind: "det", sub: "no credential · invalid plan" }),

    node("evidence", 572, 130, 240, 70, "evidence_window(start, end)", { kind: "det", sub: "validated observations" }),
    node("semantic", 572, 226, 240, 56, "cosineDistance ranking", { kind: "det", sub: "candidates only" }),
    node("fallback", 572, 310, 240, 56, "passage fallback", { kind: "det", sub: "when observations are empty" }),
    node("coverage", 860, 180, 224, 70, "evaluate_coverage", { kind: "det", sub: "per requirement" }),
    node("gap", 860, 300, 224, 70, "gap round", { kind: "llm", sub: "widen terms, same window" }),

    node("agree", 1156, 122, 216, 56, "author_date_matrix", { kind: "det", sub: "corroboration" }),
    node("media", 1156, 196, 216, 56, "media_assets FINAL", { kind: "det", sub: "rights filter" }),
    node("route", 1156, 270, 216, 56, "route_waypoints", { kind: "det" }),
    node("verify", 1156, 356, 216, 70, "verify_asset", { kind: "det", sub: "HIGH · SINGLE_SOURCE\nINTERPRETIVE · REJECTED" }),
    node("inspect", 1412, 356, 200, 70, "visual inspection", { kind: "llm", sub: "≤ 2 per board" }),

    node("board", 1156, 540, 260, 70, "ResearchBoard", { kind: "terminal", sub: "plan + coverage attached" }),
    node("events", 572, 540, 300, 70, "research_events", { kind: "store", sub: "plan_created · coverage_evaluated\ngap_replan · memory_updated · mcp_tool_call" }),
    node("sse", 100, 540, 300, 70, "GET /events", { kind: "ext", sub: "SSE replay from ClickHouse" }),
  ],
  edges: [
    { from: "post", to: "session" },
    { from: "post", to: "plan" },
    { from: "plan", to: "built" },
    { from: "plan", to: "static", color: "red", points: [[394, 202], [394, 338]], label: "model error\nvalidation failure", at: [252, 300] },
    { from: "static", to: "built", muted: true, points: [[470, 338], [470, 294]] },
    { from: "built", to: "evidence", points: [[502, 258], [536, 258], [536, 165], [570, 165]] },
    { from: "built", to: "semantic", points: [[502, 260], [536, 260], [536, 254], [570, 254]] },
    { from: "evidence", to: "coverage", points: [[812, 165], [836, 165], [836, 205], [858, 205]] },
    { from: "semantic", to: "coverage", points: [[812, 254], [836, 254], [836, 215], [858, 215]] },
    { from: "evidence", to: "fallback", color: "red", points: [[600, 202], [600, 308]], label: "no rows", at: [600, 295] },
    { from: "fallback", to: "coverage", points: [[812, 338], [836, 338], [836, 225], [858, 225]] },
    { from: "coverage", to: "gap", label: "gaps", at: [1046, 275] },
    { from: "gap", to: "coverage", points: [[858, 335], [820, 335], [820, 400], [972, 400], [972, 372]], label: "round 2, bounded", at: [880, 400] },
    { from: "coverage", to: "agree", points: [[1084, 200], [1120, 200], [1120, 150], [1154, 150]] },
    { from: "coverage", to: "media", points: [[1084, 212], [1120, 212], [1120, 224], [1154, 224]] },
    { from: "coverage", to: "route", points: [[1084, 224], [1120, 224], [1120, 298], [1154, 298]] },
    { from: "media", to: "verify", points: [[1264, 254], [1264, 354]] },
    { from: "verify", to: "inspect", label: "interpretive only", at: [1452, 330] },
    { from: "inspect", to: "verify", muted: true, points: [[1512, 428], [1512, 460], [1264, 460], [1264, 428]] },
    { from: "verify", to: "board", points: [[1264, 428], [1264, 538]] },
    {
      from: "gap", to: "events", muted: true,
      points: [[900, 372], [900, 500], [740, 500], [740, 538]],
      label: "every stage emits", at: [820, 486],
    },
    { from: "events", to: "sse", muted: true, label: "durable replay" },
    { from: "board", to: "events", muted: true, points: [[1154, 575], [880, 575]] },
  ],
  legend: ["det", "llm", "ext", "store", "state", "terminal"],
  notes: [
    "Three retrieval paths reach the same coverage step; only the first produces validated observations.",
    "Agreement, media, and route load concurrently under one asyncio.gather.",
    "A gap round writes discovered vocabulary back; a failed write emits memory_write_failed and the board still returns.",
    "Drawn 2026-09-05 from feat/ui-redesign.",
  ],
});
