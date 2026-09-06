"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { formatDate, type BoardSummary, type ResearchScope } from "./types";

const CANONICAL_PROMPT =
  "Crossing the Bitterroot Mountains, September 1805. I need terrain, weather, what they were eating, and what the horses were doing.";

/**
 * The front door: what SourceCut reads, a brief to run, and the corpus windows
 * it already covers. It holds no board — a scope card navigates to that scope's
 * captured board, and a submitted brief navigates to a live session that runs
 * on arrival, so the workspace is the one place a board is ever rendered.
 */
export default function SourceCutLanding({
  scopes = [],
  boards = [],
}: {
  scopes?: ResearchScope[];
  boards?: BoardSummary[];
}) {
  const [prompt, setPrompt] = useState(CANONICAL_PROMPT);
  const byScope = new Map(boards.map((board) => [board.scope_id, board]));

  function research(event: FormEvent) {
    event.preventDefault();
    const brief = prompt.trim();
    if (!brief) return;
    window.location.href = `/board/live?q=${encodeURIComponent(brief)}`;
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
          <span className="cut-pill">
            {boards.length} captured board{boards.length === 1 ? "" : "s"}
          </span>
          <span className="cut-pill live"><i />ClickHouse MCP · read-only</span>
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
              <button className="cut-button" type="submit">Begin scene investigation</button>
            </div>
          </form>
          <p className="cut-syntax">
            <b>Syntax tips:</b> quote period spelling exactly to search it verbatim — “disagreeable”,
            “musquetoes”. A live run takes about ninety seconds and needs the API reachable; the
            captured boards below open instantly.
          </p>
        </section>

        <section className="cut-section" aria-labelledby="scopes-title">
          <div className="cut-section-head">
            <div>
              <p className="label label-gold">Curated corpus windows</p>
              <h2 id="scopes-title">Scenes the corpus already covers.</h2>
            </div>
            <p className="label">
              {boards.length} of {scopes.length} with a captured board
            </p>
          </div>
          <div className="cut-scenarios">
            {scopes.map((scope, index) => {
              const captured = byScope.get(scope.scope_id);
              const href = captured
                ? `/board/${scope.scope_id}`
                : `/board/live?q=${encodeURIComponent(`${scope.title}. ${scope.notes}`)}`;
              return (
                <a className="cut-scenario" key={scope.scope_id} href={href}>
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
                  {captured && (
                    <div className="cut-scenario-stats">
                      <span>
                        <b>{captured.met}</b>/{captured.requirements} requirements covered
                      </span>
                      <span><b>{captured.citations}</b> passages cited</span>
                    </div>
                  )}
                  <div className="cut-scenario-foot">
                    <span className="label tabular">{scope.scope_id}</span>
                    <span>{captured ? "Open board →" : "Run this brief →"}</span>
                  </div>
                </a>
              );
            })}
          </div>
        </section>

        <footer className="cut-footer">
          <div>
            <span className="label">Journals · Gutenberg 8419</span>
            <span className="label">References · Library of Congress</span>
            <span className="label">Public-domain and CC0 only</span>
          </div>
        </footer>
      </div>
    </main>
  );
}
