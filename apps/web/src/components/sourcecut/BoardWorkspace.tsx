"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import PrevisPanel, { type PrevisSection } from "./PrevisPanel";
import EvidenceTimeline from "./EvidenceTimeline";
import {
  API,
  STATUS_LABEL,
  formatCaptureDate,
  formatDate,
  type Asset,
  type Board,
  type BoardSummary,
  type Evidence,
  type ExampleBoard,
  type Requirement,
  type TimelineEvent,
} from "./types";

/**
 * The research workspace: one board at a time, with every captured board
 * listed alongside it.
 *
 * It renders in two modes from the same markup. A captured board arrives
 * prerendered as `example` and needs no backend at all. A live session arrives
 * with `liveQuery` and runs on mount, streaming its trace into the same
 * timeline the capture would have recorded.
 */
export default function BoardWorkspace({
  example = null,
  boards = [],
  liveQuery = null,
}: {
  example?: ExampleBoard | null;
  boards?: BoardSummary[];
  liveQuery?: string | null;
}) {
  const [sessionId, setSessionId] = useState("");
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
  // The workspace shows one requirement at a time rather than stacking all
  // five, so the extracts, the matrix and the archive column agree on subject.
  const [activeId, setActiveId] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [brokenThumbnails, setBrokenThumbnails] = useState<ReadonlySet<string>>(new Set());

  const showingExample = example !== null && state === "idle";
  const scopeId = board?.plan?.scope_id ?? "";

  // A live session runs once, on arrival, from the query the landing page put
  // in the URL. Everything else on this page is prerendered and static.
  useEffect(() => {
    if (!liveQuery) return;
    let live = true;
    let stream: EventSource | null = null;
    setState("running");
    setError("");
    (async () => {
      try {
        const response = await fetch(`${API}/api/research`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: liveQuery, public_domain_only: true }),
        });
        if (!response.ok) throw new Error("The research session could not start.");
        const started = await response.json();
        if (!live) return;
        setSessionId(started.session_id);
        stream = new EventSource(`${API}${started.events_url}`);
        stream.addEventListener("progress", (message) => {
          const item = JSON.parse((message as MessageEvent).data) as TimelineEvent;
          setEvents((current) => [...current, item]);
        });
        stream.addEventListener("done", async () => {
          stream?.close();
          try {
            const result = await fetch(`${API}/api/research/${started.session_id}`).then((value) =>
              value.json(),
            );
            if (result.status !== "complete") throw new Error(result.error || "Research failed.");
            if (!live) return;
            setBoard(result.board);
            setState("complete");
          } catch (reason) {
            if (!live) return;
            setError(reason instanceof Error ? reason.message : "Research failed.");
            setState("error");
          }
        });
        stream.onerror = () => {
          stream?.close();
          if (!live) return;
          setError("The live research timeline disconnected. Run the brief again.");
          setState("error");
        };
      } catch (reason) {
        if (!live) return;
        setError(reason instanceof Error ? reason.message : "Research could not be completed.");
        setState("error");
      }
    })();
    return () => {
      live = false;
      stream?.close();
    };
  }, [liveQuery]);

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

  const listed = boards.filter((item) =>
    filter.trim() === ""
      ? true
      : `${item.title} ${item.scope_id}`.toLowerCase().includes(filter.trim().toLowerCase()),
  );

  /** Example thumbnails are copied next to the web app, so they survive the API being down. */
  function thumbnailSrc(assetId: string) {
    const captured = showingExample ? example?.asset_thumbnails[assetId] : undefined;
    return (
      captured ??
      `${API}/api/research/${sessionId}/assets/${encodeURIComponent(assetId)}/thumbnail`
    );
  }

  // A thumbnail can 404 — a prerendered board has no API behind it, and a
  // captured run may not have copied every image. A failed load falls back to
  // the empty well rather than the browser's broken-image glyph.
  function Thumbnail({ asset }: { asset: Asset["asset"] }) {
    if (!asset.thumbnail_path || brokenThumbnails.has(asset.asset_id)) {
      return <span>No preview</span>;
    }
    return (
      <img
        src={thumbnailSrc(asset.asset_id)}
        alt={asset.title}
        loading="lazy"
        onError={() => setBrokenThumbnails((current) => new Set(current).add(asset.asset_id))}
      />
    );
  }

  return (
    <div className={`sourcecut cut-workspace${sidebarOpen ? " open" : ""}`}>
      <a className="skip-link" href="#main-content">Skip to the board</a>

      <aside className="cut-rail" aria-label="Research boards">
        <div className="cut-rail-head">
          <a className="wordmark" href="/">SourceCut</a>
          <span className="cut-stamp">ARCHIVE</span>
        </div>

        <a className="cut-rail-new" href="/">
          <span>+ New research board</span>
        </a>

        <label className="sr-only" htmlFor="board-filter">Search boards</label>
        <input
          id="board-filter"
          className="cut-rail-search"
          type="search"
          placeholder="Search boards…"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
        />

        {liveQuery && (
          <>
            <p className="cut-rail-label">Live session</p>
            <div className="cut-rail-item active">
              <strong>{board?.plan?.title ?? "Running…"}</strong>
              <span className="tabular">
                {state === "running" ? "researching" : state === "error" ? "failed" : "complete"}
              </span>
            </div>
          </>
        )}

        <p className="cut-rail-label">
          Captured boards{filter.trim() ? ` · ${listed.length} of ${boards.length}` : ""}
        </p>
        <nav className="cut-rail-list">
          {listed.map((item) => (
            <a
              key={item.scope_id}
              className={`cut-rail-item${item.scope_id === scopeId && !liveQuery ? " active" : ""}`}
              href={`/board/${item.scope_id}`}
              aria-current={item.scope_id === scopeId && !liveQuery ? "page" : undefined}
            >
              <strong>{item.title}</strong>
              <span className="tabular">
                {formatDate(item.window_start)} → {formatDate(item.window_end)}
              </span>
              <span className="cut-rail-stats">
                <b className={item.met === item.requirements ? "full" : ""}>
                  {item.met}/{item.requirements}
                </b>{" "}
                covered · {item.citations} cites
              </span>
            </a>
          ))}
          {listed.length === 0 && <p className="cut-rail-empty">No board matches “{filter}”.</p>}
        </nav>

        <div className="cut-rail-foot">
          <span className="cut-pill live"><i />ClickHouse MCP · read-only</span>
        </div>
      </aside>

      <button
        type="button"
        className="cut-rail-toggle"
        aria-expanded={sidebarOpen}
        onClick={() => setSidebarOpen((open) => !open)}
      >
        {sidebarOpen ? "Close boards" : "Boards"}
      </button>

      <main id="main-content" className="cut-main">
        <header className="cut-slate">
          <div className="cut-slate-left">
            <span className="label">
              {liveQuery ? "Live session" : "Captured board"}
              {board?.plan ? ` · ${board.plan.scope_id}` : ""}
            </span>
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
              <span className="cut-pill">Round {coverage.rounds} / {coverage.rounds}</span>
            )}
            <span className={`cut-pill ${state === "running" ? "running" : "live"}`}>
              <i />
              {state === "running" ? "Researching" : "ClickHouse MCP · read-only"}
            </span>
          </div>
        </header>

        {state === "running" && !board && (
          <p className="cut-running" role="status">
            Investigating the archive. The trace below is the run as it happens.
          </p>
        )}

        {error && <p className="cut-error" role="alert">{error}</p>}

        {showingExample && example && (
          <aside className="example-banner">
            <p>
              <strong>Worked example</strong>
              A real run captured on {formatCaptureDate(example.captured_at)} and kept as it came
              out. Nothing here was written by hand.
            </p>
            <span>session {example.session_id}</span>
          </aside>
        )}

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
                  <p className="label">Requirements<br />defended</p>
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
          <section className="cut-section cut-trace" aria-live="polite" aria-label="Execution trace">
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
                  <svg viewBox="0 0 800 360" role="img" aria-label="Curated route waypoints">
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
      </main>

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
    </div>
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
 * alone when the API is unreachable — which it is on a prerendered board.
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
