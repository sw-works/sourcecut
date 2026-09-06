"use client";

import { useEffect, useState } from "react";
import BoardWorkspace from "./BoardWorkspace";
import type { BoardSummary } from "./types";

/**
 * The live session's shell. The brief travels in the query string, which only
 * exists in the browser, so the run cannot start until after hydration — the
 * page is prerendered like every other and reads its own URL on mount.
 */
export default function LiveBoard({ boards = [] }: { boards?: BoardSummary[] }) {
  const [query, setQuery] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const brief = new URLSearchParams(window.location.search).get("q");
    setQuery(brief && brief.trim() ? brief.trim() : null);
    setReady(true);
  }, []);

  if (!ready) return null;

  if (!query) {
    return (
      <div className="sourcecut cut-workspace">
        <main id="main-content" className="cut-main">
          <p className="cut-error" role="alert">
            This page runs a brief that arrives in the URL, and none was given.{" "}
            <a href="/">Write one on the front page.</a>
          </p>
        </main>
      </div>
    );
  }

  return <BoardWorkspace boards={boards} liveQuery={query} />;
}
