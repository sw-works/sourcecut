/** The board payload shapes the research surface renders, shared by the
 *  landing page, the board workspace and the evidence timeline. */

export type TimelineEvent = {
  sequence: number;
  event_id?: string;
  event_type: string;
  stage: string;
  status: string;
  message: string;
  payload: { row_count?: number; tool?: string; sql?: string; terms?: Record<string, string[]> };
  duration_ms: number;
};

export type Evidence = {
  observation_id: string;
  passage_id: string;
  author_display_name: string;
  entry_date: number;
  category: string;
  canonical_term: string;
  source_quote: string;
  confidence: number;
};

export type AgreementCell = {
  author_id: string;
  author_display_name: string;
  entry_date: number;
  state: "mentions" | "entry_without_mention" | "no_entry";
  passage_ids: string[];
};

export type Requirement = {
  requirement_id: string;
  title: string;
  category: string;
  production_need: string;
  search_terms: string[];
  evidence: Evidence[];
  agreement?: AgreementCell[];
  corroboration_authors?: number;
  corroboration_days?: number;
};

export type Asset = {
  asset: {
    asset_id: string;
    provider: string;
    title: string;
    asset_type: string;
    creation_date_text: string;
    source_url: string;
    thumbnail_path: string;
    rights_status: string;
    rights_text: string;
  };
  requirement_id: string;
  confidence: string;
  production_use: string;
  why_selected: string;
  evidence: Evidence[];
  historical_relationship: string;
  visual_inspection?: { relevant: boolean; visible_findings: string } | null;
};

/** One planned requirement, scored against its own success criterion (ADR-020). */
export type CoverageEntry = {
  requirement_id: string;
  category: string;
  status: "met" | "single_source" | "unmet";
  evidence_count: number;
  author_count: number;
  minimum_authors: number;
  success_criteria: string;
};

export type Plan = {
  scope_id: string;
  title: string;
  window_start: number;
  window_end: number;
  rationale: string;
  requirements: { category: string; title: string; search_terms: string[] }[];
  planner: string;
};

export type Waypoint = {
  waypoint_id: string;
  entry_date: number;
  name: string;
  lat: number;
  lon: number;
  citation_passage_ids: string[];
  source_note: string;
  evidence_count: number;
};

export type Board = {
  title: string;
  summary: string;
  evidence_matrix: Requirement[];
  sections: { title: string; assets: Asset[] }[];
  reviewed_assets: Asset[];
  warnings: string[];
  sources_used: string[];
  route_waypoints?: Waypoint[];
  plan?: Plan | null;
  coverage?: { entries: CoverageEntry[]; rounds: number } | null;
};

/** A real run captured at build time by `sourcecut-capture-example`. */
export type ExampleBoard = {
  session_id: string;
  captured_at: string;
  prompt: string;
  board: Board;
  events: TimelineEvent[];
  asset_thumbnails: Record<string, string>;
};

/** A curated corpus window from data/reference/research_scopes.json. */
export type ResearchScope = {
  scope_id: string;
  title: string;
  window_start: number;
  window_end: number;
  keywords: string[];
  notes: string;
  default?: boolean;
};

/** Just enough of a captured board to list it in the sidebar without shipping
 *  every board's full payload to every page. */
export type BoardSummary = {
  scope_id: string;
  title: string;
  window_start: number;
  window_end: number;
  captured_at: string;
  met: number;
  requirements: number;
  citations: number;
};

export const API = "/sourcecut-api";

export const STATUS_LABEL: Record<CoverageEntry["status"], string> = {
  met: "Covered",
  single_source: "One author only",
  unmet: "Not supported",
};

export function formatDate(value: number) {
  const text = String(value);
  return `${text.slice(0, 4)}–${text.slice(4, 6)}–${text.slice(6, 8)}`;
}

export function formatCaptureDate(value: string) {
  const captured = new Date(value);
  return Number.isNaN(captured.valueOf())
    ? value
    : captured.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
}

/** The summary the sidebar lists, derived from a full captured board. */
export function summarise(captured: ExampleBoard): BoardSummary {
  const coverage = captured.board.coverage;
  const passages = new Set<string>();
  for (const requirement of captured.board.evidence_matrix) {
    for (const item of requirement.evidence) passages.add(item.passage_id);
  }
  return {
    scope_id: captured.board.plan?.scope_id ?? "",
    title: captured.board.plan?.title ?? captured.board.title,
    window_start: captured.board.plan?.window_start ?? 0,
    window_end: captured.board.plan?.window_end ?? 0,
    captured_at: captured.captured_at,
    met: coverage?.entries.filter((entry) => entry.status === "met").length ?? 0,
    requirements: coverage?.entries.length ?? 0,
    citations: passages.size,
  };
}
