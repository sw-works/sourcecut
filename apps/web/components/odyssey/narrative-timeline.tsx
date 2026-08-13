"use client";

import { useEffect, useMemo, useState } from "react";
import styles from "../../app/odyssey/odyssey.module.css";

const API = "/sourcecut-api/api/v1";
type Passage = { book: number; line_start: number; line_end: number; relationship: string };
type Event = { event_id: string; title: string; summary: string; event_type: string; reading_order_start: number; story_order_start: string; duration_value: number | null; duration_unit: string; duration_certainty: string; duration_source_note: string; narrative_level: string; narrator_entity_id: string; participant_entity_ids: string[]; place_ids: string[]; theme_ids: string[]; passages: Passage[] };
type Timeline = { mode: "reading" | "story"; events: Event[]; coverage_books: number[]; ordering_notice: string };

export default function NarrativeTimeline() {
  const [reading, setReading] = useState<Timeline | null>(null);
  const [story, setStory] = useState<Timeline | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [character, setCharacter] = useState("");
  const [place, setPlace] = useState("");
  const [level, setLevel] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const query = new URLSearchParams();
    if (character) query.append("characters", character);
    if (place) query.append("places", place);
    if (level) query.append("narrative_levels", level);
    Promise.all(["reading", "story"].map(async (mode) => {
      const response = await fetch(`${API}/timelines/odyssey?mode=${mode}&${query}`);
      if (!response.ok) throw new Error("The reviewed narrative release is unavailable.");
      return response.json() as Promise<Timeline>;
    })).then(([nextReading, nextStory]) => { setReading(nextReading); setStory(nextStory); setError(""); })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Timeline unavailable."));
  }, [character, place, level]);

  const events = reading?.events ?? [];
  const characters = useMemo(() => [...new Set(events.flatMap((item) => item.participant_entity_ids))].sort(), [events]);
  const places = useMemo(() => [...new Set(events.flatMap((item) => item.place_ids))].sort(), [events]);
  const levels = useMemo(() => [...new Set(events.map((item) => item.narrative_level))].sort(), [events]);

  return <div className={styles.timelinePage}>
    <header className={styles.timelineHero}><p className={styles.eyebrow}>Two orders, one poem</p><h1>When it happens.<br />When it is told.</h1><p>The left column follows the poem’s reading order. The right reconstructs a curated story sequence—without inventing historical dates.</p></header>
    <section className={styles.timelineControls} aria-label="Timeline comparison filters">
      <label>Character<select value={character} onChange={(event) => setCharacter(event.target.value)}><option value="">All characters</option>{characters.map((item) => <option key={item}>{item}</option>)}</select></label>
      <label>Place<select value={place} onChange={(event) => setPlace(event.target.value)}><option value="">All places</option>{places.map((item) => <option key={item}>{item}</option>)}</select></label>
      <label>Narrative level<select value={level} onChange={(event) => setLevel(event.target.value)}><option value="">All levels</option>{levels.map((item) => <option key={item}>{item}</option>)}</select></label>
      <p>{reading ? `${reading.coverage_books.length} books represented` : "Loading reviewed release…"}</p>
    </section>
    {error && <p className={styles.readerError} role="alert">{error}</p>}
    <section className={styles.dualTimeline} aria-label="Synchronized reading and story timelines">
      <TimelineColumn title="Reading timeline" notice="Sequence of disclosure in Books 1–24" timeline={reading} selected={selected} onSelect={setSelected} />
      <TimelineColumn title="Story timeline" notice="Curated ordinal reconstruction, not dates" timeline={story} selected={selected} onSelect={setSelected} />
    </section>
  </div>;
}

function TimelineColumn({ title, notice, timeline, selected, onSelect }: { title: string; notice: string; timeline: Timeline | null; selected: string; onSelect: (id: string) => void }) {
  return <section className={styles.timelineColumn}><header><p className={styles.eyebrow}>{notice}</p><h2>{title}</h2></header><ol>{timeline?.events.map((item) => {
    const passage = item.passages[0];
    return <li key={item.event_id} className={selected === item.event_id ? styles.selectedEvent : ""}><button onClick={() => onSelect(item.event_id)}><span>{passage ? `Od. ${passage.book}.${passage.line_start}–${passage.line_end}` : "No passage"}</span><strong>{item.title}</strong><small>{item.narrative_level.replaceAll("_", " ")} · {passage?.relationship}</small></button>{selected === item.event_id && <article><p>{item.summary}</p><dl><div><dt>Narrator</dt><dd>{item.narrator_entity_id}</dd></div><div><dt>Duration</dt><dd>{item.duration_value === null ? "unknown" : `${item.duration_value} ${item.duration_unit} · ${item.duration_certainty}`}</dd></div></dl>{item.duration_source_note && <p>{item.duration_source_note}</p>}{passage && <a href={`/odyssey/read/${passage.book}?lines=${passage.line_start}-${passage.line_end}`}>Open exact Greek passage →</a>}</article>}</li>;
  })}</ol>{timeline && <footer>{timeline.ordering_notice}</footer>}</section>;
}
