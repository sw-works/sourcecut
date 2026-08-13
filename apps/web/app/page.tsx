"use client";

import { useMemo, useState } from "react";
import type { FormEvent } from "react";
import PrevisPanel, { type PrevisSection } from "./previs-panel";

const API = "/sourcecut-api";
const CANONICAL_PROMPT =
  "Build a historically grounded visual research board for the Corps of Discovery crossing the Bitterroot Mountains in September 1805. Focus on terrain, weather, transportation, food, clothing/equipment, and route geography.";

type TimelineEvent = {
  sequence: number;
  event_id: string;
  event_type: string;
  stage: string;
  status: string;
  message: string;
  payload: { row_count?: number; tool?: string };
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
type Requirement = {
  requirement_id: string;
  title: string;
  category: string;
  production_need: string;
  search_terms: string[];
  evidence: Evidence[];
  agreement?: {
    author_id: string;
    author_display_name: string;
    entry_date: number;
    state: "mentions" | "entry_without_mention" | "no_entry";
    passage_ids: string[];
  }[];
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
};

export default function Home() {
  const [prompt, setPrompt] = useState(CANONICAL_PROMPT);
  const [sessionId, setSessionId] = useState("");
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [board, setBoard] = useState<Board | null>(null);
  const [selected, setSelected] = useState<Asset | null>(null);
  const [previsSection, setPrevisSection] = useState<PrevisSection | null>(null);
  const [previsOpen, setPrevisOpen] = useState(false);
  const [state, setState] = useState<"idle" | "running" | "complete" | "error">("idle");
  const [error, setError] = useState("");
  const [routeIndex, setRouteIndex] = useState(0);

  const interpreted = useMemo(
    () => board?.reviewed_assets.filter((item) => item.confidence === "INTERPRETIVE").length ?? 0,
    [board],
  );

  async function research(event: FormEvent) {
    event.preventDefault();
    setState("running");
    setEvents([]);
    setBoard(null);
    setSelected(null);
    setPrevisSection(null);
    setPrevisOpen(false);
    setError("");
    setRouteIndex(0);
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
    <main id="main-content">
      <a className="skip-link" href="#research-input">Skip to research input</a>
      <header className="masthead">
        <a className="wordmark" href="#main-content" aria-label="SourceCut home">SourceCut</a>
        <span>Historical evidence for production</span>
        <span className="system-state"><i /> MCP runtime</span>
      </header>

      <section className="hero" aria-labelledby="hero-title">
        <p className="eyebrow">Evidence before aesthetics</p>
        <h1 id="hero-title">Make creative decisions<br />history can defend.</h1>
        <p className="hero-copy">Primary-source testimony, archival references, and rights—assembled into one traceable research board.</p>
        <form id="research-input" onSubmit={research}>
          <label htmlFor="prompt">Production research brief</label>
          <textarea id="prompt" value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={4} />
          <button type="submit" disabled={state === "running"}>
            {state === "running" ? "Investigating the archive…" : "Build research board"}
          </button>
        </form>
      </section>

      {(events.length > 0 || state === "running") && (
        <section className="timeline" aria-live="polite" aria-label="Live research timeline">
          <div className="section-heading"><p>Live trace</p><h2>The investigation</h2></div>
          <ol>
            {events.map((item) => (
              <li key={item.sequence} className={item.status}>
                <span>{String(item.sequence).padStart(2, "0")}</span>
                <div>
                  <strong>{item.event_type.replaceAll("_", " ")}</strong>
                  <p>
                    {item.message}
                    {typeof item.payload.row_count === "number"
                      ? ` ${item.payload.row_count} rows · ${item.duration_ms}ms`
                      : ""}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </section>
      )}

      {error && <p className="error" role="alert">{error}</p>}

      {board && (
        <>
          <section className="matrix" aria-labelledby="matrix-title">
            <div className="section-heading"><p>Evidence matrix</p><h2 id="matrix-title">What the journals require</h2></div>
            <div className="matrix-list">
              {board.evidence_matrix.map((item, index) => (
                <article key={item.requirement_id}>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <div>
                    <h3>{item.title}</h3><p>{item.production_need}</p>
                    <small>{item.corroboration_authors ?? 0} authors · {item.corroboration_days ?? 0} days</small>
                  </div>
                  <details>
                    <summary>{item.evidence.length} source excerpts</summary>
                    {item.evidence.slice(0, 3).map((evidence) => (
                      <blockquote key={evidence.observation_id}>
                        “{evidence.source_quote}”
                        <cite>{evidence.author_display_name} · {formatDate(evidence.entry_date)} · {evidence.passage_id}</cite>
                      </blockquote>
                    ))}
                    {(item.agreement?.length ?? 0) > 0 && (
                      <div className="agreement-grid" role="grid" aria-label={`${item.title} author and date agreement`}>
                        {item.agreement?.map((cell) => {
                          const label = cell.state === "mentions" ? "mentions" : cell.state === "entry_without_mention" ? "entry, silent" : "no entry";
                          const content = <span>{cell.author_display_name.split(" ").at(-1)} · {String(cell.entry_date).slice(-2)} · {label}</span>;
                          return cell.passage_ids[0] ? (
                            <a role="gridcell" className={cell.state} key={`${cell.author_id}-${cell.entry_date}`} href={`${API}/api/passages/${encodeURIComponent(cell.passage_ids[0])}`} target="_blank" rel="noreferrer">{content}</a>
                          ) : (
                            <span role="gridcell" className={cell.state} key={`${cell.author_id}-${cell.entry_date}`}>{content}</span>
                          );
                        })}
                      </div>
                    )}
                  </details>
                </article>
              ))}
            </div>
          </section>

          {(board.route_waypoints?.length ?? 0) >= 2 && (
            <section className="route" aria-labelledby="route-title">
              <div className="section-heading"><p>Route reference</p><h2 id="route-title">Across the Bitterroots</h2></div>
              <div className="route-map">
                <svg viewBox="0 0 800 360" role="img" aria-label="Curated September 1805 route waypoints">
                  <polyline points={board.route_waypoints!.map((point) => `${60 + ((-114 - point.lon) / 2.3) * 680},${45 + ((46.8 - point.lat) / .55) * 270}`).join(" ")} />
                  {board.route_waypoints!.map((point, index) => {
                    const x = 60 + ((-114 - point.lon) / 2.3) * 680;
                    const y = 45 + ((46.8 - point.lat) / .55) * 270;
                    return <g key={point.waypoint_id} className={index === routeIndex ? "active" : ""} onClick={() => setRouteIndex(index)} tabIndex={0} role="button" aria-label={`${point.name}, ${formatDate(point.entry_date)}, ${point.evidence_count} evidence items`} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") setRouteIndex(index); }}><circle cx={x} cy={y} r={5 + Math.min(point.evidence_count, 8)} /><text x={x + 12} y={y - 10}>{point.name}</text></g>;
                  })}
                </svg>
                <input aria-label="Route date" type="range" min="0" max={board.route_waypoints!.length - 1} value={routeIndex} onChange={(event) => setRouteIndex(Number(event.target.value))} />
                <div className="route-note">
                  <strong>{board.route_waypoints![routeIndex]?.name}</strong>
                  <span>{formatDate(board.route_waypoints![routeIndex]?.entry_date)}</span>
                  <p>{board.route_waypoints![routeIndex]?.source_note}</p>
                  {board.route_waypoints![routeIndex]?.citation_passage_ids.map((passageId) => <a key={passageId} href={`${API}/api/passages/${encodeURIComponent(passageId)}`} target="_blank" rel="noreferrer">Open cited passage ↗</a>)}
                </div>
              </div>
              <p className="route-caption">Route positions are modern scholarly reference data cited per waypoint—not extracted historical evidence. No map tiles or external runtime data are used.</p>
            </section>
          )}

          <section className="board" aria-labelledby="board-title">
            <div className="board-heading">
              <div className="section-heading"><p>Research board</p><h2 id="board-title">{board.title}</h2></div>
              <p>{interpreted} references are visibly marked interpretive—not expedition proof.</p>
            </div>
            {board.sections.map((section) => (
              <div className="board-section" key={section.title}>
                <div className="board-section-heading">
                  <h3>{section.title}</h3>
                  <button type="button" onClick={() => { setPrevisSection(section); setPrevisOpen(true); }}>Create previs <span>↗</span></button>
                </div>
                <div className="asset-grid">
                  {section.assets.map((item) => (
                    <button className="asset" key={`${section.title}-${item.asset.asset_id}`} onClick={() => setSelected(item)}>
                      <div className="image-well">
                        {item.asset.thumbnail_path ? (
                          <img src={`${API}/api/research/${sessionId}/assets/${encodeURIComponent(item.asset.asset_id)}/thumbnail`} alt={item.asset.title} />
                        ) : <span>No preview</span>}
                      </div>
                      <div className="asset-copy"><span className={`confidence ${item.confidence.toLowerCase()}`}>{item.confidence}</span><h4>{item.asset.title}</h4><p>{item.asset.creation_date_text || "Date unknown"} · {item.asset.asset_type}</p></div>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </section>
        </>
      )}

      {selected && (
        <aside className="inspector" aria-label="Asset and source drill-down">
          <button className="close" onClick={() => setSelected(null)} aria-label="Close asset details">×</button>
          <p className="eyebrow">Asset → evidence</p>
          <h2>{selected.asset.title}</h2>
          <p className={`confidence ${selected.confidence.toLowerCase()}`}>{selected.confidence}</p>
          <dl><div><dt>Relationship</dt><dd>{selected.historical_relationship.replaceAll("_", " ")}</dd></div><div><dt>Rights</dt><dd>{selected.asset.rights_status.replaceAll("_", " ")}</dd></div></dl>
          <p>{selected.why_selected}</p>
          {selected.evidence.slice(0, 3).map((item) => (
            <blockquote key={item.observation_id}>“{item.source_quote}”<cite>{item.author_display_name} · {formatDate(item.entry_date)}<br />{item.passage_id}</cite></blockquote>
          ))}
          <a href={selected.asset.source_url} target="_blank" rel="noreferrer">Open Library of Congress record ↗</a>
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

function formatDate(value: number) {
  const text = String(value);
  return `${text.slice(0, 4)}–${text.slice(4, 6)}–${text.slice(6, 8)}`;
}
