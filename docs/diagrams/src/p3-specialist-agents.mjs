import { diagram, node } from "./svg.mjs";
// Pattern 3 — multi-agent separation by tool access (agents/research.py::build_research_pipeline,
// ADR-022). The interesting part of this picture is the two boxes with no line to the tools.
export default () => diagram({
  width: 1340, height: 560,
  title: "Pattern 3 · Multi-agent — specialists separated by tool access",
  subtitle: "Three stages hand off through named output keys. Only the middle one holds tools, so the other two physically cannot fetch evidence.",
  nodes: [
    node("brief", 40, 140, 180, 60, "research question", { kind: "ext" }),
    node("planner", 254, 140, 180, 60, "sourcecut_planner", { kind: "llm", sub: "research_plan", badge: "no tools" }),
    node("research", 468, 140, 180, 60, "sourcecut_evidence", { kind: "llm", sub: "research_findings" }),
    node("auditor", 682, 140, 180, 60, "sourcecut_auditor", { kind: "llm", sub: "research_audit", badge: "no tools" }),
    node("out", 896, 140, 200, 60, "audited brief", { kind: "terminal", sub: "cited or withdrawn" }),
    node("guard", 448, 290, 220, 56, "run_query guardrail", { kind: "security", sub: "before_tool_callback" }),
    node("mcp", 448, 400, 220, 56, "mcp-clickhouse", { kind: "ext", sub: "read-only role" }),
  ],
  edges: [
    { from: "brief", to: "planner" },
    { from: "planner", to: "research", label: "plan" },
    { from: "research", to: "auditor", label: "findings" },
    { from: "auditor", to: "out" },
    { from: "research", to: "guard", label: "run_query", at: [612, 243] },
    { from: "guard", to: "mcp" },
    {
      from: "mcp", to: "research", muted: true,
      points: [[690, 428], [730, 428], [730, 262], [600, 262], [600, 202]],
      label: "rows", at: [730, 232],
    },
  ],
  legend: ["ext", "llm", "det", "security", "terminal"],
  notes: [
    "The planner cannot smuggle a historical claim in as a plan, and the auditor cannot fetch evidence to justify one it should have flagged.",
    "Separation is wiring, not instruction: an instruction to not look things up is only followed until it is not.",
    "Opt in with sourcecut-research --pipeline; the single-agent runtime is still the default.",
  ],
});
