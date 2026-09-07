"use client";

import { type SubmitEvent, useState } from "react";
import ProjectSwitcher, { type ProjectLink } from "./ProjectSwitcher";
import { formatDate, type BoardSummary } from "./types";

type Stage = {
  key: string;
  label: string;
  state: "done" | "partial" | "empty";
  summary: string;
  counts: [string, number][];
};

type Window = { scope_id: string; title: string; span: string; captured: boolean };

export type Pipeline = {
  corpus_id: string;
  title: string;
  description: string;
  status: string;
  display_policy: string;
  licenses: string[];
  sources: string[];
  stages: Stage[];
  windows: Window[];
  known_limitations: string[];
};

/** Odyssey has no research boards; it has surfaces, and they are its work. */
const ODYSSEY_SURFACES = [
  { href: "/odyssey/read/1", title: "Read", note: "Greek and translation in parallel, cited by line" },
  { href: "/odyssey/search", title: "Search", note: "Repeated formulae across the poem" },
  { href: "/odyssey/timeline", title: "Timeline", note: "Reading order against story order" },
  { href: "/odyssey/voyage", title: "Voyage", note: "Competing route proposals, kept apart" },
  { href: "/odyssey/entities", title: "Entities", note: "People, places and objects" },
  { href: "/odyssey/themes", title: "Themes", note: "Passages gathered by theme" },
  { href: "/odyssey/visual-culture", title: "Visuals", note: "Reception in museum collections" },
];

export default function ProjectDashboard({
  pipeline,
  boards = [],
  projects,
}: {
  pipeline: Pipeline;
  boards?: BoardSummary[];
  projects: ProjectLink[];
}) {
  const [prompt, setPrompt] = useState("");
  const [railOpen, setRailOpen] = useState(false);
  const isJournals = pipeline.corpus_id === "lewis-and-clark";
  const byScope = new Map(boards.map((board) => [board.scope_id, board]));

  function research(event: SubmitEvent) {
    event.preventDefault();
    const brief = prompt.trim();
    if (brief) window.location.href = `/board/live?q=${encodeURIComponent(brief)}`;
  }

  return (
    <div className={`sourcecut cut-workspace${railOpen ? " rail-open" : ""}`}>
      <button
        type="button"
        className="cut-rail-toggle"
        aria-expanded={railOpen}
        onClick={() => setRailOpen((open) => !open)}
      >
        {railOpen ? "Close" : "Project"}
      </button>

      <aside className="cut-rail" aria-label="Project">
        <div className="cut-rail-head">
          <a className="wordmark" href="/">SourceCut</a>
          <span className="cut-stamp">ARCHIVE</span>
        </div>

        <ProjectSwitcher current={pipeline.corpus_id} projects={projects} />

        {isJournals ? (
          <>
            <a className="cut-rail-new" href="#research-input">
              <span>+ New research board</span>
            </a>
            <p className="label cut-rail-group">Research boards</p>
            {boards.map((board) => (
              <a
                key={board.scope_id}
                className="cut-rail-item"
                href={`/board/${board.scope_id}`}
              >
                <b>{board.title}</b>
                <span className="label tabular">
                  {formatDate(board.window_start)} → {formatDate(board.window_end)}
                </span>
                <span className="label">
                  <b className={board.met === board.requirements ? "covered" : "single"}>
                    {board.met}/{board.requirements}
                  </b>{" "}
                  covered · <b className="tabular">{board.citations}</b> cites
                </span>
              </a>
            ))}
            {pipeline.windows
              .filter((window) => !byScope.has(window.scope_id))
              .map((window) => (
                <span key={window.scope_id} className="cut-rail-item pending">
                  <b>{window.title}</b>
                  <span className="label">no board captured yet</span>
                </span>
              ))}
          </>
        ) : (
          <>
            <p className="label cut-rail-group">Surfaces</p>
            {ODYSSEY_SURFACES.map((surface) => (
              <a key={surface.href} className="cut-rail-item" href={surface.href}>
                <b>{surface.title}</b>
                <span className="label">{surface.note}</span>
              </a>
            ))}
          </>
        )}

        <a className="cut-rail-projects label" href="/projects">
          How this corpus was built →
        </a>
      </aside>

      <main id="main-content" className="cut-main">
        <header className="cut-slate">
          <div className="cut-slate-left">
            <span className="label">{pipeline.corpus_id}</span>
          </div>
          <div className="cut-slate-right">
            <span className={`cut-pill ${pipeline.status === "active" ? "live" : ""}`}>
              <i />
              {pipeline.status}
            </span>
            <span className="cut-pill">{pipeline.display_policy.replaceAll("_", " ")}</span>
          </div>
        </header>

        <section className="cut-project-hero" aria-labelledby="project-title">
          <h1 id="project-title">{pipeline.title}</h1>
          <p className="cut-lede">{pipeline.description}</p>
          <div className="cut-stage-strip">
            {pipeline.stages.map((stage) => (
              <span key={stage.key} className={stage.state}>
                <b>{stage.label}</b>
                {stage.counts.length > 0 && (
                  <span className="tabular">
                    {stage.counts[0][1].toLocaleString()} {stage.counts[0][0]}
                  </span>
                )}
              </span>
            ))}
          </div>
        </section>

        {isJournals ? (
          <section className="cut-console" aria-label="Research brief">
            <div className="cut-console-head">
              <p className="label label-gold">New investigation brief</p>
              <p className="label">{pipeline.windows.length} curated windows</p>
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
                <button className="cut-button" type="submit">Begin scene investigation</button>
              </div>
            </form>
            <p className="cut-syntax">
              <b>Syntax tips:</b> quote period spelling exactly to search it verbatim —
              “disagreeable”, “musquetoes”. A live run takes about ninety seconds and needs the
              API reachable; the boards in the rail open instantly.
            </p>
          </section>
        ) : (
          <section className="cut-section" aria-labelledby="surfaces-title">
            <div className="cut-section-head">
              <div>
                <p className="label label-gold">Where to start</p>
                <h2 id="surfaces-title">A poem is read, not dated.</h2>
              </div>
            </div>
            <p className="cut-lede" style={{ maxWidth: "68ch" }}>
              This corpus is addressed by book and line rather than by day, so it opens on the text
              itself. Its route is three competing proposals held apart from the poem's own
              sequence, and its timeline runs in two orders at once — the order you read, and the
              order things happened.
            </p>
            <div className="cut-scenarios">
              {ODYSSEY_SURFACES.map((surface) => (
                <a className="cut-scenario" key={surface.href} href={surface.href}>
                  <div className="cut-scenario-head">
                    <span className="label label-gold">{surface.title}</span>
                  </div>
                  <h3>{surface.note}</h3>
                  <span className="label">Open →</span>
                </a>
              ))}
            </div>
          </section>
        )}

        <section className="cut-section" aria-labelledby="provenance-title">
          <div className="cut-section-head">
            <div>
              <p className="label label-gold">Provenance</p>
              <h2 id="provenance-title">What this project is made of.</h2>
            </div>
          </div>
          <div className="cut-project-foot">
            <div>
              <p className="label">Sources</p>
              <ul className="cut-project-list">
                {pipeline.sources.map((source) => <li key={source}>{source}</li>)}
              </ul>
            </div>
            <div>
              <p className="label">Rights</p>
              <ul className="cut-project-list">
                {pipeline.licenses.map((license) => <li key={license}>{license}</li>)}
                <li>{pipeline.display_policy.replaceAll("_", " ")}</li>
              </ul>
            </div>
            {pipeline.known_limitations.length > 0 && (
              <div>
                <p className="label">Known limits</p>
                <ul className="cut-project-list">
                  {pipeline.known_limitations.map((limit) => <li key={limit}>{limit}</li>)}
                </ul>
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
