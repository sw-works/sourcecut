"use client";

import { useMemo, useRef, useState } from "react";

/**
 * Three bands over one shared date axis, driven entirely by the board payload:
 * citation density, per-day corroboration, and the waypoint the party was at.
 *
 * The axis is the expedition's calendar, not wall-clock time, so a "day" here
 * is a journal entry date (YYYYMMDD) and every band indexes the same day list.
 * Band B reuses the agreement matrix's encoding — gold means someone wrote the
 * term down — so a reader who has learned one grid can read the strip.
 */

type Evidence = {
  observation_id: string;
  entry_date: number;
};

type AgreementCell = {
  author_id: string;
  entry_date: number;
  state: "mentions" | "entry_without_mention" | "no_entry";
};

type Waypoint = {
  waypoint_id: string;
  entry_date: number;
  name: string;
};

export type TimelineBoard = {
  evidence_matrix: { evidence: Evidence[]; agreement?: AgreementCell[] }[];
  reviewed_assets: { evidence: Evidence[] }[];
  route_waypoints?: Waypoint[];
  plan?: { window_start: number; window_end: number } | null;
};

/** How much of the brief the day's journals corroborate, strongest first. */
type DayState = "full" | "most" | "thin" | "none" | "no_entry";

type Day = {
  date: number;
  citations: number;
  /** Requirements two or more authors independently wrote down that day. */
  corroborated: number;
  /** Requirements at least one author wrote down. */
  attested: number;
  /** Authors who kept a journal at all, corroborating or not. */
  writing: number;
  state: DayState;
  waypoint: Waypoint | null;
};

const DAY_MS = 86_400_000;
/** A guard against a malformed window turning into an unbounded loop. */
const MAX_DAYS = 400;
const VIEW_WIDTH = 1000;
const CURVE_HEIGHT = 64;
/** Top inset keeping the peak clear of the band label. */
const CURVE_INSET = 20;
/** Below this share of the axis a label has no room for even a stem. Wider
 * blocks that still overflow are ellipsised by CSS, which reads as truncation
 * rather than as a different place name. */
const MIN_LABEL_SHARE = 0.05;

/** About this many dated ticks fit across the axis before they collide. */
const TICK_TARGET = 8;

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const STATE_LABEL: Record<DayState, string> = {
  full: "every requirement corroborated",
  most: "most requirements corroborated",
  thin: "some requirements corroborated",
  none: "journals kept, nothing corroborated",
  no_entry: "no journal entry that day",
};

/** Legend order, strongest first; only the states a board actually uses show. */
const STATE_ORDER: DayState[] = ["full", "most", "thin", "none", "no_entry"];

export default function EvidenceTimeline({
  board,
  selectedDate,
  onSelectDate,
}: {
  board: TimelineBoard;
  selectedDate: number | null;
  onSelectDate: (date: number | null) => void;
}) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<number | null>(null);

  const days = useMemo(() => buildDays(board), [board]);

  const maxCitations = useMemo(
    () => days.reduce((peak, day) => Math.max(peak, day.citations), 0),
    [days],
  );
  const curve = useMemo(() => buildCurve(days, maxCitations), [days, maxCitations]);
  const segments = useMemo(() => buildSegments(days), [days]);
  const scored = board.evidence_matrix.filter(
    (requirement) => (requirement.agreement?.length ?? 0) > 0,
  ).length;
  const fullDays = days.filter((day) => day.state === "full").length;
  // Without dates on the axis the strip is a picture, not a timeline: a reader
  // can see a thin patch but cannot say when it was. Every first-of-month gets
  // a tick whatever the spacing, because that is where the eye orients.
  const ticks = useMemo(() => buildTicks(days), [days]);
  // A legend key for a state this board never reaches teaches nothing.
  const present = STATE_ORDER.filter((state) => days.some((day) => day.state === state));

  // Two days is the least that can carry a curve, a strip and a waypoint run.
  if (days.length < 2) return null;

  const selectedIndex = days.findIndex((day) => day.date === selectedDate);
  const activeIndex = hover ?? (selectedIndex >= 0 ? selectedIndex : -1);
  const active = activeIndex >= 0 ? days[activeIndex] : null;

  function selectAt(clientX: number) {
    const track = trackRef.current;
    if (!track) return;
    const bounds = track.getBoundingClientRect();
    if (bounds.width === 0) return;
    const ratio = (clientX - bounds.left) / bounds.width;
    const index = Math.min(days.length - 1, Math.max(0, Math.floor(ratio * days.length)));
    onSelectDate(days[index].date);
  }

  function step(delta: number) {
    const from = selectedIndex >= 0 ? selectedIndex : 0;
    const next = Math.min(days.length - 1, Math.max(0, from + delta));
    onSelectDate(days[next].date);
  }

  function onKeyDown(event: React.KeyboardEvent) {
    const moves: Record<string, number> = {
      ArrowRight: 1,
      ArrowUp: 1,
      ArrowLeft: -1,
      ArrowDown: -1,
      PageUp: 7,
      PageDown: -7,
    };
    if (event.key in moves) {
      event.preventDefault();
      step(moves[event.key]);
    } else if (event.key === "Home") {
      event.preventDefault();
      onSelectDate(days[0].date);
    } else if (event.key === "End") {
      event.preventDefault();
      onSelectDate(days[days.length - 1].date);
    }
  }

  return (
    <section className="cut-section" aria-labelledby="timeline-title">
      <div className="cut-section-head">
        <div>
          <p className="label">Record density</p>
          <h2 id="timeline-title">What the journals cover, day by day.</h2>
        </div>
        <div className="cut-tally">
          <b>
            {fullDays} <span>of {days.length}</span>
          </b>
          <p className="label">
            Days corroborating all {scored} requirement{scored === 1 ? "" : "s"}
          </p>
        </div>
      </div>

      <div className="cut-timeline">
        <div
          ref={trackRef}
          className="cut-timeline-track"
          role="slider"
          tabIndex={0}
          aria-label="Expedition date"
          aria-valuemin={days[0].date}
          aria-valuemax={days[days.length - 1].date}
          aria-valuenow={selectedIndex >= 0 ? days[selectedIndex].date : days[0].date}
          aria-valuetext={
            active
              ? `${formatDate(active.date)}, ${active.citations} citations, ${STATE_LABEL[active.state]}`
              : undefined
          }
          onKeyDown={onKeyDown}
          onClick={(event) => selectAt(event.clientX)}
          onMouseMove={(event) => {
            const track = trackRef.current;
            if (!track) return;
            const bounds = track.getBoundingClientRect();
            if (bounds.width === 0) return;
            const ratio = (event.clientX - bounds.left) / bounds.width;
            setHover(Math.min(days.length - 1, Math.max(0, Math.floor(ratio * days.length))));
          }}
          onMouseLeave={() => setHover(null)}
        >
          {selectedIndex >= 0 && (
            <div
              className="cut-playhead"
              style={{ left: `${((selectedIndex + 0.5) / days.length) * 100}%` }}
            />
          )}

          <div className="cut-band-curve">
            <svg
              viewBox={`0 0 ${VIEW_WIDTH} ${CURVE_HEIGHT}`}
              preserveAspectRatio="none"
              aria-hidden="true"
            >
              <path className="area" d={curve.area} />
              <path className="line" d={curve.line} />
            </svg>
            <span className="cut-band-tag">
              Citations per day{maxCitations > 0 ? ` · peak ${maxCitations}` : ""}
            </span>
          </div>

          <div
            className="cut-band-strip"
            style={{ gridTemplateColumns: `repeat(${days.length}, 1fr)` }}
          >
            {days.map((day) => (
              <i
                key={day.date}
                className={day.state}
                // The fill is the fraction of the brief corroborated, so a
                // thinning record reads as a falling bar, not just a hue shift.
                style={{
                  "--fill": `${scored > 0 ? (day.corroborated / scored) * 100 : 0}%`,
                } as React.CSSProperties}
                title={`${formatDate(day.date)}: ${day.corroborated} of ${scored} corroborated`}
              />
            ))}
          </div>

          <div className="cut-band-route">
            {segments.map((segment) => (
              <button
                type="button"
                key={segment.waypoint.waypoint_id}
                style={{
                  left: `${(segment.start / days.length) * 100}%`,
                  width: `${(segment.length / days.length) * 100}%`,
                }}
                className={
                  activeIndex >= segment.start && activeIndex < segment.start + segment.length
                    ? "active"
                    : ""
                }
                title={`${segment.waypoint.name}, from ${formatDate(days[segment.start].date)}`}
                onClick={(event) => {
                  event.stopPropagation();
                  onSelectDate(days[segment.start].date);
                }}
              >
                {/* A block too narrow to hold its name truncates to something
                    ambiguous — two Clearwater waypoints both read "Clearwat" —
                    so it carries the name on hover and in the readout instead. */}
                {segment.length / days.length >= MIN_LABEL_SHARE && (
                  <span>{segment.waypoint.name}</span>
                )}
              </button>
            ))}
          </div>

          <div className="cut-band-axis" aria-hidden="true">
            {ticks.map((tick) => (
              <span
                key={tick.index}
                className={[
                  tick.monthStart ? "month" : "",
                  tick.index === 0 ? "first" : "",
                  tick.index === days.length - 1 ? "last" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
                style={{ left: `${((tick.index + 0.5) / days.length) * 100}%` }}
              >
                {tick.label}
              </span>
            ))}
          </div>
        </div>

        <div className="cut-timeline-read">
          <div className="cut-read-nav">
            <button
              type="button"
              onClick={() => step(-1)}
              disabled={selectedIndex === 0}
              aria-label="Previous day"
            >
              ‹
            </button>
            <span className="tabular">
              {selectedIndex >= 0 ? `day ${selectedIndex + 1} of ${days.length}` : `${days.length} days`}
            </span>
            <button
              type="button"
              onClick={() => step(1)}
              disabled={selectedIndex === days.length - 1}
              aria-label="Next day"
            >
              ›
            </button>
          </div>

          <div className="cut-read-body" aria-live="polite">
            {active ? (
              <>
                <strong className="tabular">{formatDate(active.date)}</strong>
                <span className={`state ${active.state}`}>
                  {active.corroborated} of {scored} corroborated
                </span>
                <p>
                  {active.citations} citation{active.citations === 1 ? "" : "s"} ·{" "}
                  {active.writing} author{active.writing === 1 ? "" : "s"} writing
                  {active.waypoint ? ` · ${active.waypoint.name}` : ""}
                </p>
              </>
            ) : (
              <p>Click the axis, or arrow along it, to hold a date. The board follows it.</p>
            )}
          </div>

          {selectedIndex >= 0 && (
            <button type="button" className="cut-read-clear" onClick={() => onSelectDate(null)}>
              Release date
            </button>
          )}
        </div>
      </div>

      <p className="cut-legend">
        {present.map((state) => (
          <span key={state}>
            <i className={state} /> {STATE_LABEL[state]}
          </span>
        ))}
      </p>
      <p className="cut-timeline-caption">
        Both bands are computed from the citations the board is already built on. Corroboration is
        counted per requirement: two authors writing about different things on the same day have
        corroborated neither. A thin day is a gap in the record, not a gap in the search.
      </p>
    </section>
  );
}

/** The window the board declares, widened to cover any date it actually cites. */
function buildDays(board: TimelineBoard): Day[] {
  const citationsByDay = new Map<number, Set<string>>();
  const observed: number[] = [];

  for (const group of [...board.evidence_matrix, ...board.reviewed_assets]) {
    for (const item of group.evidence ?? []) {
      observed.push(item.entry_date);
      const bucket = citationsByDay.get(item.entry_date) ?? new Set<string>();
      bucket.add(item.observation_id);
      citationsByDay.set(item.entry_date, bucket);
    }
  }

  // Corroboration is a property of one requirement on one day: two authors who
  // each wrote down a different requirement have not corroborated either. So
  // authors are counted per requirement first, and the day reports how much of
  // the brief cleared the bar — not whether anything did.
  const corroborated = new Map<number, number>();
  const attested = new Map<number, number>();
  const writing = new Map<number, Set<string>>();
  const scored = board.evidence_matrix.filter(
    (requirement) => (requirement.agreement?.length ?? 0) > 0,
  );

  for (const requirement of scored) {
    const authorsByDay = new Map<number, Set<string>>();
    for (const cell of requirement.agreement ?? []) {
      observed.push(cell.entry_date);
      if (cell.state === "no_entry") continue;
      const present = writing.get(cell.entry_date) ?? new Set<string>();
      present.add(cell.author_id);
      writing.set(cell.entry_date, present);
      if (cell.state !== "mentions") continue;
      const authors = authorsByDay.get(cell.entry_date) ?? new Set<string>();
      authors.add(cell.author_id);
      authorsByDay.set(cell.entry_date, authors);
    }
    for (const [date, authors] of authorsByDay) {
      attested.set(date, (attested.get(date) ?? 0) + 1);
      if (authors.size >= 2) corroborated.set(date, (corroborated.get(date) ?? 0) + 1);
    }
  }

  const waypoints = [...(board.route_waypoints ?? [])].sort(
    (left, right) => left.entry_date - right.entry_date,
  );
  for (const point of waypoints) observed.push(point.entry_date);

  if (observed.length === 0) return [];
  const start = Math.min(board.plan?.window_start ?? Infinity, ...observed);
  const end = Math.max(board.plan?.window_end ?? -Infinity, ...observed);
  if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return [];

  const days: Day[] = [];
  const total = scored.length;
  for (let stamp = toUtc(start); stamp <= toUtc(end) && days.length < MAX_DAYS; stamp += DAY_MS) {
    const date = toDateKey(stamp);
    const strong = corroborated.get(date) ?? 0;
    const present = writing.get(date)?.size ?? 0;
    days.push({
      date,
      citations: citationsByDay.get(date)?.size ?? 0,
      corroborated: strong,
      attested: attested.get(date) ?? 0,
      writing: present,
      state:
        present === 0
          ? "no_entry"
          : total > 0 && strong === total
            ? "full"
            : strong * 2 >= total
              ? "most"
              : strong > 0
                ? "thin"
                : "none",
      // The waypoint in force is the last one reached on or before this day.
      waypoint: waypoints.filter((point) => point.entry_date <= date).at(-1) ?? null,
    });
  }
  return days;
}

/** Dated ticks for the axis: every first-of-month, plus an even spread between
 *  them, plus the two ends — enough to place a day without crowding the row. */
function buildTicks(days: Day[]) {
  const stride = Math.max(1, Math.ceil(days.length / TICK_TARGET));
  // A month boundary is the anchor a reader looks for, so it is placed first
  // and the evenly spread ticks fill in around it. A candidate closer than most
  // of a stride to something already placed is dropped: two dates sharing the
  // same few pixels are less legible than one.
  const placed: number[] = [];
  const clear = (index: number) =>
    placed.every((taken) => Math.abs(taken - index) >= stride * 0.7);

  days.forEach((day, index) => {
    if (day.date % 100 === 1) placed.push(index);
  });
  for (const index of [0, days.length - 1]) if (clear(index)) placed.push(index);
  for (let index = 0; index < days.length; index += stride) {
    if (clear(index)) placed.push(index);
  }

  return placed
    .sort((left, right) => left - right)
    .map((index) => {
      const text = String(days[index].date);
      const month = MONTHS[Number(text.slice(4, 6)) - 1] ?? "";
      const dayOfMonth = text.slice(6, 8);
      const monthStart = index === 0 || days[index].date % 100 === 1;
      return { index, monthStart, label: monthStart ? `${month} ${dayOfMonth}` : dayOfMonth };
    });
}

function buildCurve(days: Day[], peak: number) {
  if (days.length < 2) return { line: "", area: "" };
  const step = VIEW_WIDTH / days.length;
  // The run is drawn edge to edge: the first and last days own half a step of
  // width each, so the area does not open with a wedge of empty ground.
  const at = (index: number) =>
    index === 0 ? 0 : index === days.length - 1 ? VIEW_WIDTH : index * step + step / 2;
  const points = days.map((day, index) => {
    const height = peak > 0 ? (day.citations / peak) * (CURVE_HEIGHT - CURVE_INSET) : 0;
    return `${at(index).toFixed(1)},${(CURVE_HEIGHT - height).toFixed(1)}`;
  });
  const line = `M ${points.join(" L ")}`;
  return {
    line,
    area: `${line} L ${VIEW_WIDTH},${CURVE_HEIGHT} L 0,${CURVE_HEIGHT} Z`,
  };
}

/** Contiguous runs of days sharing a waypoint, for the bottom band's blocks. */
function buildSegments(days: Day[]) {
  const segments: { waypoint: Waypoint; start: number; length: number }[] = [];
  days.forEach((day, index) => {
    if (!day.waypoint) return;
    const open = segments.at(-1);
    if (open && open.waypoint.waypoint_id === day.waypoint.waypoint_id) {
      open.length += 1;
      return;
    }
    segments.push({ waypoint: day.waypoint, start: index, length: 1 });
  });
  return segments;
}

function toUtc(value: number) {
  const text = String(value);
  return Date.UTC(
    Number(text.slice(0, 4)),
    Number(text.slice(4, 6)) - 1,
    Number(text.slice(6, 8)),
  );
}

function toDateKey(stamp: number) {
  const moment = new Date(stamp);
  return (
    moment.getUTCFullYear() * 10000 + (moment.getUTCMonth() + 1) * 100 + moment.getUTCDate()
  );
}

function formatDate(value: number) {
  const text = String(value);
  return `${text.slice(0, 4)}–${text.slice(4, 6)}–${text.slice(6, 8)}`;
}
