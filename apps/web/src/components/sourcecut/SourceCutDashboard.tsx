"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import PrevisPanel, { type PrevisSection } from "./PrevisPanel";
import EvidenceTimeline from "./EvidenceTimeline";

const API = "/sourcecut-api";
const CANONICAL_PROMPT =
  "Crossing the Bitterroot Mountains, September 1805. I need terrain, weather, what they were eating, and what the horses were doing.";

type TimelineEvent = {
  sequence: number;
  event_id?: string;
  event_type: string;
  stage: string;
  status: string;
  message: string;
  payload: { row_count?: number; tool?: string; sql?: string; terms?: Record<string, string[]> };
  duration_ms: number;
};
type Evidence = {
  observation_id: string;
  passage_id: string;
  author_display_name: string;
  entry_date: number;
  category: string;
  canonical_term: string;
  source_quote: string;
  confidence: number;
};
type AgreementCell = {
  author_id: string;
  author_display_name: string;
  entry_date: number;
  state: "mentions" | "entry_without_mention" | "no_entry";
  passage_ids: string[];
};
type Requirement = {
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
type Asset = {
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
type CoverageEntry = {
  requirement_id: string;
  category: string;
  status: "met" | "single_source" | "unmet";
  evidence_count: number;
  author_count: number;
  minimum_authors: number;
  success_criteria: string;
};
type Plan = {
  scope_id: string;
  title: string;
  window_start: number;
  window_end: number;
  rationale: string;
  requirements: { category: string; title: string; search_terms: string[] }[];
  planner: string;
};
type Board = {
  title: string;
  summary: string;
  evidence_matrix: Requirement[];
  sections: { title: string; assets: Asset[] }[];
  reviewed_assets: Asset[];
  warnings: string[];
  sources_used: string[];
  route_waypoints?: {
    waypoint_id: string;
    entry_date: number;
    name: string;
    lat: number;
    lon: number;
    citation_passage_ids: string[];
    source_note: string;
    evidence_count: number;
  }[];
  plan?: Plan | null;
  coverage?: { entries: CoverageEntry[]; rounds: number } | null;
};

/** A real run captured at build time by `sourcecut-capture-example`. */
type ExampleBoard = {
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

const STATUS_LABEL: Record<CoverageEntry["status"], string> = {
  met: "Covered",
  single_source: "One author only",
  unmet: "Not supported",
};

export default function Home({
  examples = [],
  scopes = [],
}: {
  examples?: ExampleBoard[];
  scopes?: ResearchScope[];
}) {
  // One captured board per curated scope. The first is the default scope's,
  // and the directory switches between them without a network call.
  const [exampleIndex, setExampleIndex] = useState(0);
  const example = examples[exampleIndex] ?? null;
  const byScope = useMemo(() => {
    const index = new Map<string, number>();
    examples.forEach((captured, position) => {
      const scope = captured.board.plan?.scope_id;
      if (scope && !index.has(scope)) index.set(scope, position);
    });
    return index;
  }, [examples]);

  const [prompt, setPrompt] = useState(examples[0]?.prompt ?? CANONICAL_PROMPT);
  const [sessionId, setSessionId] = useState("");
  // The example's board and timeline stand in until a live run starts, so the
  // page shows real work with no session and no backend reachable.
  const [showingExample, setShowingExample] = useState(examples.length > 0);
  const [events, setEvents] = useState<TimelineEvent[]>(examples[0]?.events ?? []);
  const [board, setBoard] = useState<Board | null>(examples[0]?.board ?? null);
  const [selected, setSelected] = useState<Asset | null>(null);
  const [citation, setCitation] = useState<Evidence | null>(null);
  const [previsSection, setPrevisSection] = useState<PrevisSection | null>(null);
  const [previsOpen, setPrevisOpen] = useState(false);
  const [state, setState] = useState<"idle" | "running" | "complete" | "error">("idle");
  const [error, setError] = useState("");
  // The one clock the timeline, the route map and the agreement matrices share.
  const [selectedDate, setSelectedDate] = useState<number | null>(null);
  // The workspace shows one requirement at a time rather than stacking all
  // five, so the extracts, the matrix and the archive column agree on subject.
  const [activeId, setActiveId] = useState<string | null>(null);

  const coverage = board?.coverage ?? null;
  const met = coverage?.entries.filter((entry) => entry.status === "met").length ?? 0;
  const unmet = coverage?.entries.filter((entry) => entry.status === "unmet") ?? [];
  const interpreted = useMemo(
    () => board?.reviewed_assets.filter((item) => item.confidence === "INTERPRETIVE").length ?? 0,
    [board],
  );
  const waypoints = board?.route_waypoints ?? [];
  // The waypoint in force on the held date is the last one reached by then, so
  // the map and the timeline cannot disagree about where the party was.
  const routeIndex = useMemo(() => {
    if (waypoints.length === 0 || selectedDate === null) return 0;
    return Math.max(0, waypoints.filter((point) => point.entry_date <= selectedDate).length - 1);
  }, [waypoints, selectedDate]);

  const requirements = board?.evidence_matrix ?? [];
  const active =
    requirements.find((item) => item.requirement_id === activeId) ?? requirements[0] ?? null;
  const activeCoverage = coverage?.entries.find(
    (entry) => entry.requirement_id === active?.requirement_id,
  );
  const activeAssets = useMemo(
    () =>
      board?.reviewed_assets.filter((item) => item.requirement_id === active?.requirement_id) ?? [],
    [board, active],
  );
  const citedPassages = useMemo(() => {
    const seen = new Set<string>();
    for (const requirement of requirements) {
      for (const item of requirement.evidence) seen.add(item.passage_id);
    }
    return seen.size;
  }, [requirements]);

  // The widened round is the moment worth seeing: what the first pass missed,
  // and the period vocabulary the second one tried instead.
  const widened = useMemo(() => {
    const replan = events.find((item) => item.event_type === "gap_replan");
    const terms = Object.values(replan?.payload?.terms ?? {}).flat();
    return terms.length > 0 ? Array.from(new Set(terms)) : [];
  }, [events]);
  const lastSql = useMemo(
    () =>
      [...events].reverse().find((item) => typeof item.payload?.sql === "string")?.payload?.sql ?? "",
    [events],
  );

  // A thumbnail can 404 — the prerendered example has no API behind it, and a
  // captured run may not have copied every image. A failed load falls back to
  // the empty well rather than leaving the browser's broken-image glyph.
  const [brokenThumbnails, setBrokenThumbnails] = useState<ReadonlySet<string>>(new Set());
  function Thumbnail({ asset }: { asset: Asset["asset"] }) {
    if (!asset.thumbnail_path || brokenThumbnails.has(asset.asset_id)) {
      return <span>No preview</span>;
    }
    return (
      <img
        src={thumbnailSrc(asset.asset_id)}
        alt={asset.title}
        loading="lazy"
        onError={() =>
          setBrokenThumbnails((current) => new Set(current).add(asset.asset_id))
        }
      />
    );
  }

  function openCaptured(position: number) {
    const captured = examples[position];
    if (!captured) return;
    setExampleIndex(position);
    setShowingExample(true);
    setBoard(captured.board);
    setEvents(captured.events);
    setPrompt(captured.prompt);
    setSessionId("");
    setState("idle");
    setError("");
    setSelected(null);
    setCitation(null);
    setSelectedDate(null);
    setActiveId(null);
  }

  /** Example thumbnails are copied next to the web app, so they survive the API being down. */
  function thumbnailSrc(assetId: string) {
    const captured = showingExample ? example?.asset_thumbnails[assetId] : undefined;
    return (
      captured ??
      `${API}/api/research/${sessionId}/assets/${encodeURIComponent(assetId)}/thumbnail`
    );
  }

  async function research(event: FormEvent) {
    event.preventDefault();
    setState("running");
    setShowingExample(false);
    setEvents([]);
    setBoard(null);
    setSelected(null);
    setCitation(null);
    setPrevisSection(null);
    setPrevisOpen(false);
    setError("");
    setSelectedDate(null);
    setActiveId(null);
    try {
      const response = await fetch(`${API}/api/research`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: prompt, public_domain_only: true }),
      });
      if (!response.ok) throw new Error("The research session could not start.");
      const started = await response.json();
      setSessionId(started.session_id);
      const stream = new EventSource(`${API}${started.events_url}`);
      stream.addEventListener("progress", (message) => {
        const item = JSON.parse((message as MessageEvent).data) as TimelineEvent;
        setEvents((current) => [...current, item]);
      });
      stream.addEventListener("done", async () => {
        stream.close();
        try {
          const result = await fetch(`${API}/api/research/${started.session_id}`).then((value) =>
            value.json(),
          );
          if (result.status !== "complete") throw new Error(result.error || "Research failed.");
          setBoard(result.board);
          setState("complete");
        } catch (reason) {
          setError(reason instanceof Error ? reason.message : "Research failed.");
          setState("error");
        }
      });
      stream.onerror = () => {
        stream.close();
        setError("The live research timeline disconnected. Run the request again.");
        setState("error");
      };
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Research could not be completed.");
      setState("error");
    }
  }

  return (
    <main id="main-content" className="sourcecut">
      <a className="skip-link" href="#research-input">Skip to research input</a>

      <header className="cut-slate">
        <div className="cut-slate-left">
          <a className="wordmark" href="#main-content" aria-label="SourceCut home">SourceCut</a>
          <span className="cut-stamp">ARCHIVE</span>
          <span className="label">Historical evidence for production</span>
        </div>
        <div className="cut-slate-right">
          {board?.plan && (
            <span className="cut-pill">
              <span className="label">Expedition range</span>
              <b className="tabular">
                {board.plan.window_start}–{board.plan.window_end}
              </b>
            </span>
          )}
          {coverage && coverage.rounds > 0 && (
            <span className="cut-pill">
              Round {coverage.rounds} / {coverage.rounds}
            </span>
          )}
          <span className={`cut-pill ${state === "running" ? "running" : "live"}`}>
            <i />
            {state === "running" ? "Researching" : "ClickHouse MCP · read-only"}
          </span>
        </div>
      </header>

      <div className="cut-shell">
        <section className="cut-frame" aria-labelledby="hero-title">
          <span className="cut-year" aria-hidden="true">1805</span>
          <div className="cut-frame-inner">
            <p className="label label-gold">SourceCut archival engine · production research OS</p>
            <h1 id="hero-title">Design scenes from the historical record.</h1>
            <p className="cut-lede">
              SourceCut turns a production brief into defended historical evidence. It queries the
              expedition journals, verifies every quote against stored character offsets, and
              returns rights-cleared Library of Congress references you can take into an art
              department meeting.
            </p>

            <div className="cut-reads">
              <div><b>Gutenberg 8419</b><em>· verbatim journals</em></div>
              <div><b>Library of Congress</b><em>· maps and artifacts</em></div>
              <div><b>ClickHouse MCP</b><em>· vector and full-text</em></div>
              <div><b>Exact character offsets</b><em>· span-verified quotes</em></div>
            </div>

            <div className="cut-guarantee">
              <div>
                <h3>Defensibility and chain of custody</h3>
                <p>
                  Every claim on a board resolves to a stored passage with an exact quote and
                  character offsets. An observation whose span does not match its passage is never
                  marked trusted, and nothing reaches the board without a rights decision a person
                  accepted.
                </p>
              </div>
              <span className="cut-badge covered">Read-only corpus</span>
            </div>
          </div>
        </section>

        <section className="cut-console" aria-label="Research brief">
          <div className="cut-console-head">
            <p className="label label-gold">New investigation brief</p>
            <p className="label">Direct MCP semantic ingestion</p>
          </div>
          <form id="research-input" className="cut-form" onSubmit={research}>
            <label className="sr-only" htmlFor="prompt">Production research brief</label>
            <textarea
              id="prompt"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              rows={3}
              placeholder="Describe the scene you are building — period, place, and what has to be right on camera."
            />
            <div className="cut-actions">
              <div className="cut-constraints">
                <span>Public-domain and CC0 sources only</span>
                <span>Trusted observations only</span>
              </div>
              <button className="cut-button" type="submit" disabled={state === "running"}>
                {state === "running" ? "Investigating the archive…" : "Begin scene investigation"}
              </button>
            </div>
          </form>
          <p className="cut-syntax">
            <b>Syntax tips:</b> quote period spelling exactly to search it verbatim — “disagreeable”,
            “musquetoes”. Press <kbd>Enter</kbd> inside the brief for a new line; the button starts
            the run.
          </p>
        </section>

        {/* The directory is orientation, not a result: it stands while the page
            shows the worked example or nothing, and steps aside once a live run
            has produced a board of the visitor's own. */}
        {scopes.length > 0 && (showingExample || !board) && (
          <section className="cut-section" aria-labelledby="scopes-title">
            <div className="cut-section-head">
              <div>
                <p className="label label-gold">Curated corpus windows</p>
                <h2 id="scopes-title">Scenes the corpus already covers.</h2>
              </div>
              <p className="label">
                {examples.length} of {scopes.length} with a captured board
              </p>
            </div>
            <div className="cut-scenarios">
              {scopes.map((scope, index) => {
                const captured = byScope.get(scope.scope_id);
                const open = captured !== undefined && captured === exampleIndex;
                return (
                <button
                  type="button"
                  className={`cut-scenario${open ? " open" : ""}`}
                  key={scope.scope_id}
                  aria-pressed={open}
                  onClick={() => {
                    if (captured !== undefined) {
                      openCaptured(captured);
                      document.getElementById("brief-title")?.scrollIntoView({ block: "start" });
                      return;
                    }
                    setPrompt(`${scope.title}. ${scope.notes}`);
                    document.getElementById("prompt")?.focus();
                  }}
                >
                  <div className="cut-scenario-head">
                    <span className="cut-scenario-index">
                      SCOPE #{String(index + 1).padStart(2, "0")}
                    </span>
                    <span className="label tabular">
                      {formatDate(scope.window_start)} → {formatDate(scope.window_end)}
                    </span>
                  </div>
                  <h3>{scope.title}</h3>
                  <p className="cut-scenario-note">{scope.notes}</p>
                  <div className="cut-scenario-terms">
                    {scope.keywords.slice(0, 4).map((term) => (
                      <span className="cut-chip" key={term}>{term}</span>
                    ))}
                  </div>
                  <div className="cut-scenario-foot">
                    <span className="label tabular">{scope.scope_id}</span>
                    <span>
                      {captured === undefined
                        ? "Load into brief →"
                        : open
                          ? "Showing this board"
                          : "Open captured board →"}
                    </span>
                  </div>
                </button>
                );
              })}
            </div>
          </section>
        )}

        {showingExample && board && example && (
          <aside className="example-banner">
            <p>
              <strong>Worked example</strong>
              {example.board.plan?.title ?? example.board.title}, built on{" "}
              {formatCaptureDate(example.captured_at)} and kept as it came out. Submit a brief above
              to replace it with your own.
            </p>
            <span>session {example.session_id}</span>
          </aside>
        )}

        {error && <p className="cut-error" role="alert">{error}</p>}

        {board && (
          <section className="cut-section" aria-labelledby="brief-title">
            <div className="cut-brief">
              <div className="cut-brief-main">
                <p className="label label-gold">
                  Production research brief · {board.plan?.scope_id ?? "custom scope"}
                </p>
                <h2 id="brief-title">{board.plan?.title ?? board.title}</h2>
                <p className="cut-lede" style={{ fontSize: "0.8125rem" }}>{board.summary}</p>
                <div className="cut-brief-facts" style={{ marginTop: "0.9rem" }}>
                  <span><b>{citedPassages}</b> passages cited</span>
                  <span><b>{board.reviewed_assets.length}</b> references reviewed</span>
                  <span><b>{waypoints.length}</b> waypoints</span>
                  <span>planner · {board.plan?.planner ?? "static"}</span>
                </div>
              </div>

              {coverage && (
                <div className="cut-stat">
                  <span className="cut-stat-figure">
                    {met} <span>/ {coverage.entries.length}</span>
                  </span>
                  <p className="label">
                    Requirements
                    <br />
                    defended
                  </p>
                  <div className="cut-stat-roll">
                    <span className="cut-badge covered">{met} covered</span>
                    {coverage.entries.filter((entry) => entry.status === "single_source").length >
                      0 && (
                      <span className="cut-badge single_source">
                        {coverage.entries.filter((entry) => entry.status === "single_source").length}{" "}
                        single-author
                      </span>
                    )}
                    {unmet.length > 0 && (
                      <span className="cut-badge unmet">{unmet.length} unsupported</span>
                    )}
                  </div>
                  <div className="cut-stat-meta">
                    <span><b>Corpus</b>Gutenberg 8419</span>
                    <span><b>Catalog</b>{board.sources_used[0] ?? "Library of Congress"}</span>
                    <span><b>Rounds</b>{coverage.rounds}</span>
                    <span><b>Interpretive</b>{interpreted} reference{interpreted === 1 ? "" : "s"}</span>
                  </div>
                </div>
              )}
            </div>
          </section>
        )}

        {coverage && coverage.entries.length > 0 && (
          <section className="cut-section" aria-labelledby="coverage-title">
            <div className="cut-section-head">
              <div>
                <p className="label label-gold">Criterion scorecard</p>
                <h2 id="coverage-title">Scored against each requirement's own criterion.</h2>
              </div>
            </div>

            <div className="cut-coverage">
              {coverage.entries.map((entry, index) => {
                const requirement = requirements.find(
                  (item) => item.requirement_id === entry.requirement_id,
                );
                const selectedHere = entry.requirement_id === active?.requirement_id;
                return (
                  <div key={`${entry.requirement_id}-${entry.category}`} className={entry.status}>
                    <div className="cut-scenario-head">
                      <span className="cut-coverage-index">
                        {String(index + 1).padStart(2, "0")}
                      </span>
                      <span className={`cut-badge ${entry.status}`}>
                        {STATUS_LABEL[entry.status]}
                      </span>
                    </div>
                    <h3>{entry.category}</h3>
                    <p title={entry.success_criteria}>
                      {entry.status === "unmet"
                        ? "No passage in window"
                        : `${entry.author_count} author${entry.author_count === 1 ? "" : "s"} · ${entry.evidence_count} cites`}
                    </p>
                    {requirement && (
                      <button
                        type="button"
                        className="cut-previs"
                        aria-pressed={selectedHere}
                        onClick={() => setActiveId(requirement.requirement_id)}
                      >
                        {selectedHere ? "In focus" : "Open in workspace →"}
                      </button>
                    )}
                  </div>
                );
              })}
            </div>

            {widened.length > 0 && (
              <div className="cut-round">
                <span className="label label-gold">Round 2 · widened the search</span>
                <span className="cut-terms">
                  {widened.map((term) => <span key={term}>{term}</span>)}
                </span>
                <em>The window does not move</em>
              </div>
            )}
          </section>
        )}

        {(events.length > 0 || state === "running") && (
          <section
            className="cut-section cut-trace"
            aria-live="polite"
            aria-label="Execution trace"
          >
            <div className="cut-section-head">
              <div>
                <p className="label label-gold">Execution trace</p>
                <h2>Every step, and what it cost.</h2>
              </div>
              <p className="label">{showingExample ? "as captured" : "live"} · research_events</p>
            </div>
            <ol>
              {events.map((item) => (
                <li key={item.event_id ?? item.sequence} className={`${item.event_type} ${item.status}`}>
                  <span className="tabular">{String(item.sequence).padStart(2, "0")}</span>
                  <div>
                    <strong>{item.event_type.replaceAll("_", " ")}</strong>
                    <p>{item.message}</p>
                    {item.event_type === "gap_replan" && widened.length > 0 && (
                      <span className="cut-terms" style={{ marginTop: "0.4rem" }}>
                        {widened.map((term) => <span key={term}>{term}</span>)}
                      </span>
                    )}
                  </div>
                  <span className="tabular">
                    {typeof item.payload?.row_count === "number"
                      ? `${item.payload.row_count} rows`
                      : item.duration_ms
                        ? `${item.duration_ms}ms`
                        : "—"}
                  </span>
                </li>
              ))}
            </ol>
            {lastSql && (
              <>
                <p className="label" style={{ margin: "1.15rem 0 0.5rem" }}>
                  Last statement through mcp-clickhouse
                </p>
                <pre className="cut-sql">{lastSql}</pre>
              </>
            )}
          </section>
        )}

        {board && active && (
          <>
            <section className="cut-section" aria-labelledby="dossier-title">
              <div className="cut-section-head">
                <div>
                  <p className="label label-gold">
                    Active focus · {active.category} · {active.corroboration_authors ?? 0} author
                    {(active.corroboration_authors ?? 0) === 1 ? "" : "s"} ·{" "}
                    {active.corroboration_days ?? 0} days
                  </p>
                  <h2 id="dossier-title">{active.title}</h2>
                </div>
                {activeCoverage && (
                  <span className={`cut-badge ${activeCoverage.status}`}>
                    {STATUS_LABEL[activeCoverage.status]}
                  </span>
                )}
              </div>

              <div className="cut-dossier">
                <div className="cut-panel">
                  <div className="cut-panel-head">
                    <h2>Verbatim journal extracts</h2>
                    <p className="label">
                      {active.evidence.length} cites · {active.production_need}
                    </p>
                  </div>

                  <div className="cut-quotes">
                    {/* A held date pulls its own citations to the front rather
                        than hiding the rest, so the panel never looks empty. */}
                    {[...active.evidence]
                      .sort(
                        (left, right) =>
                          Number(right.entry_date === selectedDate) -
                          Number(left.entry_date === selectedDate),
                      )
                      .slice(0, 4)
                      .map((item) => (
                        <button
                          key={item.observation_id}
                          type="button"
                          onClick={() => {
                            setCitation(item);
                            setSelectedDate(item.entry_date);
                          }}
                          aria-label={`Open the stored passage behind ${item.author_display_name}'s ${formatDate(item.entry_date)} entry`}
                        >
                          <blockquote className={item.entry_date === selectedDate ? "on-date" : ""}>
                            “{item.source_quote}”
                            <cite>
                              <b>{item.author_display_name}</b>
                              <span>{formatDate(item.entry_date)}</span>
                              <span>{item.passage_id}</span>
                            </cite>
                          </blockquote>
                        </button>
                      ))}
                  </div>

                  {(active.agreement?.length ?? 0) > 0 && (
                    <AgreementMatrix
                      requirement={active}
                      selectedDate={selectedDate}
                      onSelectDate={setSelectedDate}
                    />
                  )}
                </div>

                <div className="cut-panel">
                  <div className="cut-panel-head">
                    <h2>Correlated archival references</h2>
                    <p className="label">{activeAssets.length} matched</p>
                  </div>
                  {activeAssets.length > 0 ? (
                    <>
                      <div className="cut-artifacts">
                        {activeAssets.map((item) => (
                          <button
                            className="cut-artifact"
                            key={item.asset.asset_id}
                            onClick={() => setSelected(item)}
                          >
                            <div className="well"><Thumbnail asset={item.asset} /></div>
                            <div className="cut-artifact-body">
                              <div className="cut-artifact-top">
                                <span className={`cut-badge ${item.confidence.toLowerCase()}`}>
                                  {item.confidence.replaceAll("_", " ")}
                                </span>
                                <span className="tabular">{item.asset.asset_id}</span>
                              </div>
                              <h4>{item.asset.title}</h4>
                              <p>
                                {item.asset.creation_date_text || "Date unknown"} ·{" "}
                                {item.asset.asset_type} ·{" "}
                                {item.historical_relationship.replaceAll("_", " ")}
                              </p>
                            </div>
                          </button>
                        ))}
                      </div>
                      <div className="cut-artifacts-foot">
                        <span>All references verified against Gutenberg citations</span>
                        <span>{interpreted} interpretive on this board</span>
                      </div>
                    </>
                  ) : (
                    <p className="cut-timeline-caption" style={{ marginTop: 0 }}>
                      No archive reference cleared for this requirement. Reported, not hidden.
                    </p>
                  )}
                </div>
              </div>
            </section>

            <EvidenceTimeline
              board={board}
              selectedDate={selectedDate}
              onSelectDate={setSelectedDate}
            />

            {waypoints.length >= 2 && (
              <section className="route" aria-labelledby="route-title">
                <div className="cut-section-head">
                  <div>
                    <p className="label label-gold">Route reference</p>
                    <h2 id="route-title">Where the entries were written.</h2>
                  </div>
                </div>
                <div className="route-map">
                  <svg viewBox="0 0 800 360" role="img" aria-label="Curated September 1805 route waypoints">
                    <polyline points={waypoints.map((point) => `${60 + ((-114 - point.lon) / 2.3) * 680},${45 + ((46.8 - point.lat) / .55) * 270}`).join(" ")} />
                    {waypoints.map((point, index) => {
                      const x = 60 + ((-114 - point.lon) / 2.3) * 680;
                      const y = 45 + ((46.8 - point.lat) / .55) * 270;
                      return (
                        <g
                          key={point.waypoint_id}
                          className={index === routeIndex ? "active" : ""}
                          onClick={() => setSelectedDate(point.entry_date)}
                          tabIndex={0}
                          role="button"
                          aria-label={`${point.name}, ${formatDate(point.entry_date)}, ${point.evidence_count} evidence items`}
                          onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") setSelectedDate(point.entry_date); }}
                        >
                          <circle cx={x} cy={y} r={4 + Math.min(point.evidence_count, 7)} />
                          <text x={x + 12} y={y - 10}>{point.name}</text>
                        </g>
                      );
                    })}
                  </svg>
                  <input
                    aria-label="Route date"
                    type="range"
                    min="0"
                    max={waypoints.length - 1}
                    value={routeIndex}
                    onChange={(event) => setSelectedDate(waypoints[Number(event.target.value)].entry_date)}
                  />
                  <div className="route-note">
                    <strong>{waypoints[routeIndex]?.name}</strong>
                    <span>{formatDate(waypoints[routeIndex]?.entry_date)}</span>
                    <p>{waypoints[routeIndex]?.source_note}</p>
                  </div>
                </div>
                <p className="route-caption">
                  Route positions are modern scholarly reference data cited per waypoint — not
                  extracted historical evidence.
                </p>
              </section>
            )}

            {board.sections.map((section) => (
              <section className="cut-section" key={section.title}>
                <div className="cut-refs-head">
                  <p className="label label-gold">{section.title}</p>
                  <button
                    type="button"
                    className="cut-previs"
                    onClick={() => { setPrevisSection(section); setPrevisOpen(true); }}
                  >
                    Create previs →
                  </button>
                </div>
                <div className="cut-refs">
                  {section.assets.map((item) => (
                    <button
                      className="cut-ref"
                      key={`${section.title}-${item.asset.asset_id}`}
                      onClick={() => setSelected(item)}
                    >
                      <div className="well"><Thumbnail asset={item.asset} /></div>
                      <span className={`cut-badge ${item.confidence.toLowerCase()}`}>
                        {item.confidence.replaceAll("_", " ")}
                        {item.confidence === "INTERPRETIVE" ? " · not proof" : ""}
                      </span>
                      <h4>{item.asset.title}</h4>
                      <p>{item.asset.creation_date_text || "Date unknown"} · {item.asset.asset_id}</p>
                    </button>
                  ))}
                </div>
              </section>
            ))}

            {unmet.map((entry) => (
              <div className="cut-unmet" key={entry.requirement_id}>
                <div>
                  <span className="label">{entry.category} · not supported</span>
                  <p>{entry.success_criteria}</p>
                </div>
                <div>
                  Widening found nothing inside the window.<br />
                  Reported, not hidden.
                </div>
              </div>
            ))}

            {board.warnings.length > 0 && (
              <section className="cut-section" aria-label="Board warnings">
                <div className="cut-section-head">
                  <div>
                    <p className="label label-gold">Before you use this board</p>
                    <h2>What to check.</h2>
                  </div>
                </div>
                <ul className="cut-warnings">
                  {board.warnings.map((warning) => <li key={warning}>{warning}</li>)}
                </ul>
              </section>
            )}

            <footer className="cut-footer">
              <div>
                <span className="label">Journals · Gutenberg 8419</span>
                <span className="label">
                  References · {board.sources_used[0] ?? "Library of Congress"}
                </span>
                <span className="label">
                  {interpreted} reference{interpreted === 1 ? "" : "s"} marked interpretive
                </span>
              </div>
              {sessionId && (
                <a className="label label-gold" href={`${API}/api/research/${sessionId}`}>
                  Open this board's full trace →
                </a>
              )}
            </footer>
          </>
        )}
      </div>

      {citation && <CitationInspector citation={citation} onClose={() => setCitation(null)} />}

      {selected && (
        <aside className="cut-inspector" aria-label="Reference details">
          <button className="close" onClick={() => setSelected(null)} aria-label="Close reference details">×</button>
          <p className="label label-gold">Reference → evidence</p>
          <h2>{selected.asset.title}</h2>
          <span className="passage-id">
            {selected.asset.creation_date_text || "Date unknown"} · {selected.asset.asset_id}
          </span>
          <dl className="cut-provenance">
            <dt>Confidence</dt>
            <dd>{selected.confidence.replaceAll("_", " ").toLowerCase()}</dd>
            <dt>Relationship</dt>
            <dd>{selected.historical_relationship.replaceAll("_", " ")}</dd>
            <dt>Rights</dt>
            <dd>
              {selected.asset.rights_status.replaceAll("_", " ")}
              <small>{selected.asset.rights_text}</small>
            </dd>
            <dt>Why selected</dt>
            <dd>{selected.why_selected}</dd>
            {selected.visual_inspection && (
              <>
                <dt>Visual inspection</dt>
                <dd>{selected.visual_inspection.visible_findings}</dd>
              </>
            )}
          </dl>
          <div className="cut-quotes" style={{ marginTop: "1.25rem" }}>
            {selected.evidence.slice(0, 2).map((item) => (
              <blockquote key={item.observation_id}>
                “{item.source_quote}”
                <cite>
                  <b>{item.author_display_name}</b>
                  <span>{formatDate(item.entry_date)}</span>
                  <span>{item.passage_id}</span>
                </cite>
              </blockquote>
            ))}
          </div>
          <a className="source-link" href={selected.asset.source_url} target="_blank" rel="noreferrer">
            Open the {selected.asset.provider === "loc" ? "Library of Congress" : selected.asset.provider} record ↗
          </a>
        </aside>
      )}

      <PrevisPanel
        open={previsOpen}
        sessionId={sessionId}
        section={previsSection}
        onClose={() => setPrevisOpen(false)}
        onRecover={() => setPrevisOpen(true)}
      />
    </main>
  );
}

/** Author × date presence for one requirement, linked to the passages behind it. */
function AgreementMatrix({
  requirement,
  selectedDate,
  onSelectDate,
}: {
  requirement: Requirement;
  selectedDate: number | null;
  onSelectDate: (date: number) => void;
}) {
  const cells = requirement.agreement ?? [];
  const days = Array.from(new Set(cells.map((cell) => cell.entry_date))).sort();
  const authors = Array.from(new Map(cells.map((cell) => [cell.author_id, cell.author_display_name])));
  const byKey = new Map(cells.map((cell) => [`${cell.author_id}:${cell.entry_date}`, cell]));

  return (
    <div className="cut-matrix">
      <div className="cut-matrix-head">
        <p className="label">Who wrote it down, and when</p>
        <p className="cut-legend" style={{ margin: 0 }}>
          <span><i className="mentions" /> mentions the term</span>
          <span><i /> wrote that day, silent on it</span>
          <span><i className="no_entry" /> no entry</span>
        </p>
      </div>
      <div className="cut-matrix-scroll">
        <div
          className="cut-agreement"
          role="grid"
          aria-label={`${requirement.title} author and date agreement`}
          style={{ gridTemplateColumns: `4rem repeat(${days.length}, minmax(1.35rem, 1fr))` }}
        >
          <span className="label">Day</span>
          {days.map((day) => (
            <button
              type="button"
              className={`day${day === selectedDate ? " on-date" : ""}`}
              key={`head-${day}`}
              onClick={() => onSelectDate(day)}
              aria-label={`Hold ${formatDate(day)} across the board`}
            >
              {String(day).slice(-2)}
            </button>
          ))}
          {authors.map(([authorId, name]) => (
            <Fragment key={authorId}>
              <span>{name.split(" ").at(-1)}</span>
              {days.map((day) => {
                const cell = byKey.get(`${authorId}:${day}`);
                const stateClass = cell?.state ?? "no_entry";
                const title = `${name}, ${formatDate(day)}: ${
                  stateClass === "mentions"
                    ? "mentions the term"
                    : stateClass === "entry_without_mention"
                      ? "wrote that day, silent on it"
                      : "no entry"
                }`;
                return cell?.passage_ids[0] ? (
                  <a
                    role="gridcell"
                    key={`${authorId}-${day}`}
                    className={`cell ${stateClass}${day === selectedDate ? " on-date" : ""}`}
                    title={title}
                    href={`${API}/api/passages/${encodeURIComponent(cell.passage_ids[0])}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <span className="sr-only">{title}</span>
                  </a>
                ) : (
                  <span
                    role="gridcell"
                    key={`${authorId}-${day}`}
                    className={`cell ${stateClass}${day === selectedDate ? " on-date" : ""}`}
                    title={title}
                  />
                );
              })}
            </Fragment>
          ))}
        </div>
      </div>
    </div>
  );
}

/**
 * The stored passage behind one citation, with the claimed span highlighted in
 * place. The board payload carries the quote but not the surrounding text, so
 * the passage is fetched on open and the drill-down falls back to the quote
 * alone when the API is unreachable — which it is on a prerendered example.
 */
function CitationInspector({ citation, onClose }: { citation: Evidence; onClose: () => void }) {
  const [passage, setPassage] = useState<string | null>(null);
  const [pending, setPending] = useState(true);

  useEffect(() => {
    let live = true;
    setPending(true);
    setPassage(null);
    fetch(`${API}/api/passages/${encodeURIComponent(citation.passage_id)}`)
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (!live) return;
        const text = data?.passage_text ?? data?.rows?.[0]?.passage_text ?? null;
        setPassage(typeof text === "string" ? text : null);
      })
      .catch(() => undefined)
      .finally(() => { if (live) setPending(false); });
    return () => { live = false; };
  }, [citation.passage_id]);

  const start = passage ? passage.indexOf(citation.source_quote) : -1;
  const end = start >= 0 ? start + citation.source_quote.length : -1;

  return (
    <aside className="cut-inspector" aria-label="Source drill-down">
      <button className="close" onClick={onClose} aria-label="Close source drill-down">×</button>
      <p className="label label-gold">The stored passage, unedited</p>
      <h2>{citation.author_display_name}, {formatDate(citation.entry_date)}</h2>
      <span className="passage-id">
        {citation.passage_id}
        {passage ? ` · ${passage.length} characters` : ""}
      </span>

      <div className="cut-passage">
        {start >= 0 && passage ? (
          <>
            {passage.slice(0, start)}
            <mark>{passage.slice(start, end)}</mark>
            {passage.slice(end)}
          </>
        ) : (
          <>
            “{citation.source_quote}”
            {!pending && (
              <span className="passage-id" style={{ marginTop: "0.9rem" }}>
                The surrounding passage could not be loaded; the exact stored quote is shown.
              </span>
            )}
          </>
        )}
      </div>

      <div className="cut-facts">
        <div>
          <span className="label">Span</span>
          <b className="tabular">{start >= 0 ? `${start}–${end}` : "—"}</b>
        </div>
        <div>
          <span className="label">Category</span>
          <b>{citation.category}</b>
        </div>
        <div>
          <span className="label">Term</span>
          <b>{citation.canonical_term}</b>
        </div>
        <div>
          <span className="label">Confidence</span>
          <b className="tabular">{citation.confidence.toFixed(2)}</b>
        </div>
      </div>

      {start >= 0 && (
        <div className="cut-verified">
          <span className="label">Span verified</span>
          Characters {start}–{end} of the stored passage match the quoted text exactly. An
          observation whose span does not match is never marked trusted.
        </div>
      )}
    </aside>
  );
}

function formatDate(value: number) {
  const text = String(value);
  return `${text.slice(0, 4)}–${text.slice(4, 6)}–${text.slice(6, 8)}`;
}

function formatCaptureDate(value: string) {
  const captured = new Date(value);
  return Number.isNaN(captured.valueOf())
    ? value
    : captured.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
}
