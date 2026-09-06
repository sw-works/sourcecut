import { diagram, node } from "./svg.mjs";
// Pattern 1 — plan-then-execute, as the board path does it (agents/planner.py, ADR-019).
// The model chooses a scope_id and nothing else that reaches SQL. Every window in the
// run is read from the scope file, so a plan cannot widen the corpus slice.
export default () => diagram({
  width: 1240, height: 500,
  title: "Pattern 1 · Planning — the model plans, the application retrieves",
  subtitle: "A brief becomes a typed ResearchPlan. The date window is read from a committed file, never taken from model output.",
  nodes: [
    node("brief", 40, 150, 180, 60, "filmmaker brief", { kind: "ext" }),
    node("planner", 280, 150, 200, 60, "Gemini planner", { kind: "llm", sub: "scope_id + requirements" }),
    node("build", 540, 150, 210, 60, "build_plan", { kind: "det", sub: "validate before use" }),
    node("plan", 830, 150, 230, 60, "ResearchPlan", { kind: "terminal", sub: "window · terms · criteria" }),
    node("scopes", 540, 300, 210, 56, "research_scopes.json", { kind: "store", sub: "5 curated windows" }),
    node("route", 280, 300, 200, 56, "route_scope", { kind: "det", sub: "keyword routing" }),
  ],
  edges: [
    { from: "brief", to: "planner" },
    { from: "planner", to: "build", label: "ResearchPlanDraft" },
    { from: "build", to: "plan", label: "validated" },
    { from: "scopes", to: "build", label: "window + title", at: [700, 255] },
    { from: "scopes", to: "route", label: "keywords" },
    {
      from: "build", to: "route", color: "red",
      label: "unknown scope · unsafe term\nno credential · timeout",
      points: [[560, 212], [560, 255], [380, 255], [380, 298]], at: [175, 262],
    },
    {
      from: "route", to: "plan", muted: true,
      points: [[380, 358], [380, 400], [945, 400], [945, 212]], at: [660, 400],
      label: "baseline requirements, same contract",
    },
  ],
  legend: ["ext", "llm", "det", "store", "terminal"],
  notes: [
    "Terms reach SQL as literals, so build_plan restricts them to ^[a-z0-9][a-z0-9 '-]{1,39}$ before anything is queried.",
    "Planning degrades rather than fails: with no GEMINI_API_KEY the static planner runs the same path offline.",
    "A planning call is bounded (SOURCECUT_PLANNER_TIMEOUT_SECONDS, 60s); a call that never returns takes the same fallback.",
  ],
});
