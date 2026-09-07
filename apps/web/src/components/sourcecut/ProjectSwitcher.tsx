"use client";

import { useEffect, useRef, useState } from "react";

export type ProjectLink = {
  corpus_id: string;
  title: string;
  /** A short line the switcher shows under each name. */
  note?: string;
};

/**
 * Move between corpora without going back to the front page.
 *
 * It sits at the top of the rail, where the corpus name already was, so the
 * name a reader was looking at becomes the control that changes it.
 */
export default function ProjectSwitcher({
  current,
  projects,
}: {
  current: string;
  projects: ProjectLink[];
}) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement | null>(null);
  const active = projects.find((project) => project.corpus_id === current);
  const others = projects.filter((project) => project.corpus_id !== current);

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      if (box.current && !box.current.contains(event.target as Node)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  if (others.length === 0) {
    return <p className="label cut-rail-corpus">{active?.title ?? current}</p>;
  }

  return (
    <div className="cut-switcher" ref={box}>
      <button
        type="button"
        className="cut-switcher-button"
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={() => setOpen((value) => !value)}
      >
        <span>
          <span className="label">Project</span>
          <b>{active?.title ?? current}</b>
        </span>
        <i aria-hidden="true">{open ? "▲" : "▼"}</i>
      </button>
      {open && (
        <ul className="cut-switcher-menu" role="menu">
          {projects.map((project) => (
            <li key={project.corpus_id} role="none">
              <a
                role="menuitem"
                href={`/project/${project.corpus_id}`}
                className={project.corpus_id === current ? "active" : ""}
              >
                <b>{project.title}</b>
                {project.note && <span className="label">{project.note}</span>}
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
