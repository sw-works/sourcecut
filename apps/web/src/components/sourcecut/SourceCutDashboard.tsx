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

export default function Home({ example = null }: { example?: ExampleBoard | null }) {
  const [prompt, setPrompt] = useState(example?.prompt ?? CANONICAL_PROMPT);
  const [sessionId, setSessionId] = useState("");
  // The example's board and timeline stand in until a live run starts, so the
  // page shows real work with no session and no backend reachable.
  const [showingExample, setShowingExample] = useState(example !== null);
  const [events, setEvents] = useState<TimelineEvent[]>(example?.events ?? []);
  const [board, setBoard] = useState<Board | null>(example?.board ?? null);
  const [selected, setSelected] = useState<Asset | null>(null);
  const [citation, setCitation] = useState<Evidence | null>(null);
  const [previsSection, setPrevisSection] = useState<PrevisSection | null>(null);
  const [previsOpen, setPrevisOpen] = useState(false);
  const [state, setState] = useState<"idle" | "running" | "complete" | "error">("idle");
  const [error, setError] = useState("");
  // The one clock the timeline, the route map and the agreement matrices share.
  const [selectedDate, setSelectedDate] = useState<number | null>(null);

  const waypoints = board?.route_waypoints ?? [];
  // The waypoint in force on the held date is the last one reached by then, so
  // the map and the timeline cannot disagree about where the party was.
  const routeIndex = useMemo(() => {
    if (waypoints.length === 0) return 0;
    if (selectedDate === null) return 0;
    const reached = waypoints.filter((point) => point.entry_date <= selectedDate).length;
    return Math.max(0, reached - 1);
  }, [waypoints, selectedDate]);

  const coverage = board?.coverage ?? null;
  const met = coverage?.entries.filter((entry) => entry.status === "met").length ?? 0;
  const unmet = coverage?.entries.filter((entry) => entry.status === "unmet") ?? [];
  const interpreted = useMemo(
    () => board?.reviewed_assets.filter((item) => item.confidence === "INTERPRETIVE").length ?? 0,
    [board],
  );
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
          <span className="label">Historical evidence for production</span>
        </div>
        <div className="cut-slate-right">
          {board?.plan && (
            <span className="label tabular">
              {board.plan.window_start} – {board.plan.window_end}
            </span>
          )}
          {coverage && coverage.rounds > 1 && (
            <span className="label label-gold">Round {coverage.rounds} of {coverage.rounds}</span>
          )}
          <span className={`label cut-status${state === "running" ? " running" : ""}`}>
            <i />
            {state === "running" ? "Researching" : "ClickHouse MCP · read-only"}
          </span>
        </div>
      </header>

      <section className="cut-frame" aria-labelledby="hero-title">
        <svg className="ridge" viewBox="0 0 1440 496" preserveAspectRatio="none" aria-hidden="true">
          <path
            d="M0 340 L196 224 L344 288 L502 172 L664 272 L826 186 L972 292 L1140 210 L1290 300 L1440 240 L1440 496 L0 496 Z"
            fill="oklch(16% 0.016 244)"
          />
          <path
            d="M0 396 L162 318 L340 376 L520 296 L692 370 L874 306 L1046 382 L1220 320 L1440 390 L1440 496 L0 496 Z"
            fill="oklch(12.5% 0.01 250)"
          />
        </svg>
        <div className="cut-frame-inner">
          <div>
            <h1 id="hero-title">Design the scene from the record.</h1>
            <p className="cut-lede">
              Describe the scene you are building. SourceCut plans the research, reads the
              expedition journals, and returns references you can defend in a production meeting.
            </p>
            <form id="research-input" className="cut-form" onSubmit={research}>
              <label htmlFor="prompt">Production research brief</label>
              <textarea
                id="prompt"
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                rows={3}
                placeholder="Describe your scene — period, place, and what has to be right on camera."
              />
              <div className="cut-actions">
                <button className="cut-button" type="submit" disabled={state === "running"}>
                  {state === "running" ? "Investigating the archive…" : "Build the board"}
                </button>
                <span>Public-domain and CC0 sources only</span>
              </div>
            </form>
          </div>

          <div>
            <p className="label">What it reads</p>
            <div className="cut-reads">
              <div><b>Expedition journals</b><em>Gutenberg 8419</em></div>
              <div><b>Quote-anchored observations</b><em>trusted only</em></div>
              <div><b>Archive references</b><em>Library of Congress</em></div>
              <div><b>Corpus segments</b><em>5 curated windows</em></div>
            </div>
            <p className="cut-note">
              Every claim on a board resolves to a stored passage with an exact quote and character
              offsets.
            </p>
          </div>
        </div>
      </section>

      {showingExample && board && example && (
        <aside className="example-banner">
          <p>
            <strong>Worked example</strong>
            A board built on {formatCaptureDate(example.captured_at)}, kept as it came out. Submit a
            brief above to replace it with your own.
          </p>
          <span>session {example.session_id}</span>
        </aside>
      )}

      {error && <p className="cut-error" role="alert">{error}</p>}

      {coverage && coverage.entries.length > 0 && (
        <section className="cut-section" aria-labelledby="coverage-title">
          <div className="cut-section-head">
            <div>
              <p className="label label-gold">{board?.plan?.title ?? board?.title}</p>
              <h2 id="coverage-title">Scored against each requirement's own criterion.</h2>
            </div>
            <div className="cut-tally">
              <b>{met} <span>of {coverage.entries.length}</span></b>
              <p className="label">
                Requirements covered{coverage.rounds > 1 ? ` · ${coverage.rounds} rounds` : ""}
              </p>
            </div>
          </div>

          <div className="cut-coverage">
            {coverage.entries.map((entry) => (
              <div key={entry.requirement_id} className={entry.status}>
                <p className="label state">
                  {entry.status === "met"
                    ? "Covered"
                    : entry.status === "single_source"
                      ? "One author only"
                      : "Not supported"}
                </p>
                <h3>{entry.category}</h3>
                <p title={entry.success_criteria}>
                  {entry.status === "unmet"
                    ? "No passage in window"
                    : `${entry.author_count} author${entry.author_count === 1 ? "" : "s"} · ${entry.evidence_count} cites`}
                </p>
              </div>
            ))}
          </div>

          {widened.length > 0 && (
            <div className="cut-round">
              <span className="label">Round 2 · widened the search</span>
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
          aria-label="Research timeline"
        >
          <div className="cut-section-head">
            <p className="label">{showingExample ? "Trace · as captured" : "Live trace"}</p>
            <p className="label">research_events</p>
          </div>
          <ol>
            {events.map((item) => (
              <li key={item.event_id ?? item.sequence} className={`${item.event_type} ${item.status}`}>
                <span className="tabular">{String(item.sequence).padStart(2, "0")}</span>
                <div>
                  <strong>{item.event_type.replaceAll("_", " ")}</strong>
                  <p>{item.message}</p>
                  {item.event_type === "gap_replan" && widened.length > 0 && (
                    <span className="cut-terms">
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
              <p className="label" style={{ marginTop: "1.4rem" }}>
                Last statement through mcp-clickhouse
              </p>
              <pre className="cut-sql">{lastSql}</pre>
            </>
          )}
        </section>
      )}

      {board && (
        <>
          <EvidenceTimeline
            board={board}
            selectedDate={selectedDate}
            onSelectDate={setSelectedDate}
          />

          {board.evidence_matrix.map((requirement) => (
            <section
              className="cut-section"
              key={requirement.requirement_id}
              aria-labelledby={`req-${requirement.requirement_id}`}
            >
              <div className="cut-section-head">
                <div>
                  <p className="label">
                    Evidence · {requirement.category} · {requirement.corroboration_authors ?? 0}{" "}
                    author{(requirement.corroboration_authors ?? 0) === 1 ? "" : "s"} ·{" "}
                    {requirement.corroboration_days ?? 0} days
                  </p>
                  <h2 id={`req-${requirement.requirement_id}`}>{requirement.title}</h2>
                </div>
              </div>

              <div className="cut-quotes">
                {/* A held date pulls its own citations to the front rather than
                    hiding the rest, so the section never looks empty. */}
                {[...requirement.evidence]
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
                          {item.author_display_name} · {formatDate(item.entry_date)} ·{" "}
                          {item.passage_id}
                        </cite>
                      </blockquote>
                    </button>
                  ))}
              </div>

              {(requirement.agreement?.length ?? 0) > 0 && (
                <AgreementMatrix
                  requirement={requirement}
                  selectedDate={selectedDate}
                  onSelectDate={setSelectedDate}
                />
              )}
            </section>
          ))}

          {(board.route_waypoints?.length ?? 0) >= 2 && (
            <section className="route" aria-labelledby="route-title">
              <div className="cut-section-head">
                <div>
                  <p className="label">Route reference</p>
                  <h2 id="route-title">Where the entries were written.</h2>
                </div>
              </div>
              <div className="route-map">
                <svg viewBox="0 0 800 360" role="img" aria-label="Curated September 1805 route waypoints">
                  <polyline points={board.route_waypoints!.map((point) => `${60 + ((-114 - point.lon) / 2.3) * 680},${45 + ((46.8 - point.lat) / .55) * 270}`).join(" ")} />
                  {board.route_waypoints!.map((point, index) => {
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
                        <circle cx={x} cy={y} r={5 + Math.min(point.evidence_count, 8)} />
                        <text x={x + 12} y={y - 10}>{point.name}</text>
                      </g>
                    );
                  })}
                </svg>
                <input
                  aria-label="Route date"
                  type="range"
                  min="0"
                  max={board.route_waypoints!.length - 1}
                  value={routeIndex}
                  onChange={(event) =>
                    setSelectedDate(board.route_waypoints![Number(event.target.value)].entry_date)
                  }
                />
                <div className="route-note">
                  <strong>{board.route_waypoints![routeIndex]?.name}</strong>
                  <span>{formatDate(board.route_waypoints![routeIndex]?.entry_date)}</span>
                  <p>{board.route_waypoints![routeIndex]?.source_note}</p>
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
                <span className="label">{section.title}</span>
                <button
                  type="button"
                  className="cut-previs"
                  onClick={() => { setPrevisSection(section); setPrevisOpen(true); }}
                >
                  Create previs <span>→</span>
                </button>
              </div>
              <div className="cut-refs">
                {section.assets.map((item) => (
                  <button
                    className="cut-ref"
                    key={`${section.title}-${item.asset.asset_id}`}
                    onClick={() => setSelected(item)}
                  >
                    <div className="well">
                      {item.asset.thumbnail_path ? (
                        <img src={thumbnailSrc(item.asset.asset_id)} alt={item.asset.title} />
                      ) : <span>No preview</span>}
                    </div>
                    <span className={`confidence ${item.confidence.toLowerCase()}`}>
                      {item.confidence.replaceAll("_", " ")}
                      {item.confidence === "INTERPRETIVE" ? " · not expedition proof" : ""}
                    </span>
                    <h4>{item.asset.title}</h4>
                    <p>{item.asset.creation_date_text || "Date unknown"} · {item.asset.asset_type} · {item.asset.asset_id}</p>
                  </button>
                ))}
              </div>
            </section>
          ))}

          {unmet.map((entry) => (
            <div className="cut-unmet" key={entry.requirement_id}>
              <div>
                <p className="label">{entry.category} · not supported</p>
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
              <p className="label">What to check before using this board</p>
              <ul className="cut-warnings">
                {board.warnings.map((warning) => <li key={warning}>{warning}</li>)}
              </ul>
            </section>
          )}

          <footer className="cut-footer">
            <div>
              <span className="label">Journals · Gutenberg 8419</span>
              <span className="label">References · {board.sources_used[0] ?? "Library of Congress"}</span>
              <span className="label">
                {interpreted} reference{interpreted === 1 ? "" : "s"} marked interpretive
              </span>
            </div>
            {sessionId && (
              <a className="label" href={`${API}/api/research/${sessionId}`}>
                Open this board's full trace →
              </a>
            )}
          </footer>
        </>
      )}

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
          <div className="cut-quotes" style={{ marginTop: "1.4rem" }}>
            {selected.evidence.slice(0, 2).map((item) => (
              <blockquote key={item.observation_id}>
                “{item.source_quote}”
                <cite>{item.author_display_name} · {formatDate(item.entry_date)} · {item.passage_id}</cite>
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
    <div style={{ marginTop: "1.75rem" }}>
      <p className="label">Who wrote it down, and when</p>
      <div
        className="cut-agreement"
        role="grid"
        aria-label={`${requirement.title} author and date agreement`}
        style={{ gridTemplateColumns: `4.5rem repeat(${days.length}, minmax(1.35rem, 1fr))` }}
      >
        <span />
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
      <p className="cut-legend">
        <span><i className="mentions" /> mentions the term</span>
        <span><i /> wrote that day, silent on it</span>
        <span><i className="no_entry" /> no entry</span>
      </p>
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
