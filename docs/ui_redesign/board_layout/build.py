"""Builds the three research-board layout artboards from the captured board.

Every number, quote, waypoint and day-state on these mockups is read out of
data/examples/bitterroot-september-1805.json, so a layout is judged against the
density the real board actually has rather than against invented content.
"""

import json
from pathlib import Path

BOARD = json.loads(
    Path("/Users/hanyu/dev/sourcecut/data/examples/bitterroot-september-1805.json").read_text()
)["board"]

OUT = Path(__file__).parent

# ── palette, lifted from apps/web/src/styles/sourcecut.css ──────────────
GROUND, PANEL, RECESSED, RAISED = "#0b0f14", "#121820", "#080b0e", "#1a222d"
LINE, LINE_STRONG = "#1e293b", "#334155"
TEXT, DIM, DIMMER = "#f1f5f9", "#94a3b8", "#7e8fa8"
GOLD, GOLD_BRIGHT, GOLD_DEEP = "#e0a96d", "#f4a261", "#d4a373"
GOLD_WASH, GOLD_EDGE = "rgba(224, 169, 109, 0.12)", "rgba(212, 163, 115, 0.4)"
COVERED, COVERED_WASH, COVERED_EDGE = "#2dd4bf", "rgba(45, 212, 191, 0.12)", "rgba(45, 212, 191, 0.3)"
SINGLE, SINGLE_WASH, SINGLE_EDGE = "#f59e0b", "rgba(245, 158, 11, 0.12)", "rgba(245, 158, 11, 0.3)"
INTERP = "#7e8fa8"
M_ACTIVE, M_SILENT, M_ABSENT = "#f4a261", "#263546", "#0e141b"

# Font stacks are written with SINGLE quotes inside: they are interpolated into
# double-quoted inline style attributes, and a double quote there closes the
# attribute early — which silently dropped every nowrap and colour after it.
DISPLAY = "Newsreader, 'Iowan Old Style', Georgia, serif"
BODY = "Inter, system-ui, -apple-system, sans-serif"
MONO = "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"

PANEL_BOX = f"border: 1px solid {LINE}; border-radius: 4px; background: {PANEL};"
RECESS_BOX = (
    f"border: 1px solid {LINE}; border-radius: 4px; background: {RECESSED};"
    " box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.5);"
)

# ── the board's own numbers ─────────────────────────────────────────────
DAYS = [
    (18050909, 5, 4, "most"), (18050910, 6, 5, "full"), (18050911, 5, 3, "most"),
    (18050912, 5, 4, "most"), (18050913, 5, 4, "most"), (18050914, 5, 5, "full"),
    (18050915, 1, 5, "full"), (18050916, 2, 4, "most"), (18050917, 3, 4, "most"),
    (18050918, 0, 5, "full"), (18050919, 2, 5, "full"), (18050920, 0, 4, "most"),
    (18050921, 1, 4, "most"), (18050922, 3, 5, "full"), (18050923, 2, 2, "thin"),
    (18050924, 2, 3, "most"), (18050925, 4, 4, "most"), (18050926, 0, 3, "most"),
    (18050927, 1, 3, "most"), (18050928, 1, 2, "thin"), (18050929, 1, 2, "thin"),
    (18050930, 0, 2, "thin"),
]
PEAK = 6
HELD = 10  # 1805-09-19, the day every mockup shows held

CURVE = (
    "0.0,27.3 68.2,20.0 113.6,27.3 159.1,27.3 204.5,27.3 250.0,27.3 295.5,56.7 "
    "340.9,49.3 386.4,42.0 431.8,64.0 477.3,49.3 522.7,64.0 568.2,56.7 613.6,42.0 "
    "659.1,49.3 704.5,49.3 750.0,34.7 795.5,64.0 840.9,56.7 886.4,56.7 931.8,56.7 "
    "1000.0,64.0"
)

WAYPOINTS = [
    ("Travelers' Rest", 18050909, -114.064, 46.719, 14, 0, 2),
    ("Lolo Creek", 18050911, -114.304, 46.757, 12, 2, 3),
    ("Lolo Hot Springs", 18050914, -114.532, 46.726, 23, 5, 2),
    ("Lolo Pass", 18050916, -114.580, 46.635, 12, 7, 2),
    ("Bitterroot Ridge", 18050918, -114.797, 46.536, 14, 9, 2),
    ("Camp Creek", 18050920, -115.013, 46.447, 21, 11, 1),
    ("Clearwater Descent", 18050921, -115.292, 46.342, 23, 12, 1),
    ("Weippe Prairie", 18050922, -115.938, 46.378, 23, 13, 8),
    ("Clearwater Camp", 18050930, -116.213, 46.425, 3, 21, 1),
]

TABS = [
    ("01", "Terrain", "3 auth · 12", "met"),
    ("02", "Weather", "2 auth · 6", "met"),
    ("03", "Food", "1 auth · 12", "single"),
    ("04", "Health", "1 auth · 12", "single"),
    ("05", "Transportation", "3 auth · 12", "met"),
]

AGREEMENT = {
    "Meriwether Lewis": "MM.......MMMMM........",
    "Patrick Gass": "MMMMMMMMMMMMMMssMMssss",
    "William Clark": "MMMMMMMMMMMMMMsMMsMssM",
}

QUOTES = [
    ("Set out early and proceeded on thro a plain as yesterday down the valley "
     "Crossed a large Scattering Creek on which Cotton trees grow at 11/2 miles, "
     "a Small one at 10 miles, both from the right, the main ri",
     "William Clark", "1805-09-09", "gutenberg-8419:clark:1805-09-09:1:passage:0"),
    ("n the river. The soil of the valley is poor and gravelly ; and the high "
     "snow-topped mountains are still in view on our left ; Our course generally "
     "north a few degrees west. We",
     "Patrick Gass", "1805-09-09", "archive-gasssjournalofle00gass:gass:1805-09-09:1:passage:0"),
    ("r discharged itself into the columbia river, he informed us that it "
     "continues it's course along the mountains to the N. so far as he knew it",
     "Meriwether Lewis", "1805-09-09", "gutenberg-8419:lewis:1805-09-09:1:passage:0"),
]

REFERENCES = [
    ("HIGH", "loc:2004626119", "1807 · map",
     "A map of the discoveries of Capt. Lewis & Clark from the Rockey Mountain "
     "and the River Lewis to the Cap of Disappointment"),
    ("INTERPRETIVE", "loc:91682738", "1990 · map",
     "Lewis and Clark in the Rocky Mountains"),
    ("INTERPRETIVE", "loc:mt0144", "Date unknown · photo, print, drawing",
     "Traveler's Rest-Lolo Trail, Lolo, Missoula County, MT"),
]

STATE_FILL = {"full": M_ACTIVE, "most": GOLD, "thin": GOLD_DEEP, "none": M_SILENT}


def esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ── shared atoms ────────────────────────────────────────────────────────
def head(title):
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400&display=swap">
  <style>
    body {{ margin: 0; background: {GROUND}; color: {TEXT}; font-family: {BODY}; font-size: 14px; line-height: 1.5; }}
    a {{ color: {GOLD}; text-decoration: none; }}
    a:hover {{ color: {GOLD_BRIGHT}; }}
    .lb {{ font-family: {MONO}; font-size: 11px; font-weight: 500; letter-spacing: 0.02em; text-transform: uppercase; color: {DIMMER}; }}
    .lb-gold {{ color: {GOLD}; }}
    .mn {{ font-family: {MONO}; font-variant-numeric: tabular-nums; }}
    .dp {{ font-family: {DISPLAY}; font-weight: 400; letter-spacing: -0.015em; }}
    h1, h2, h3, h4, p {{ margin: 0; font-weight: 400; }}
    /* {title} */
  </style>
</helmet>
"""


TAIL = """</x-dc>
</body>
</html>
"""


def pill(text, tone="quiet"):
    edge = {"quiet": LINE_STRONG, "live": COVERED_EDGE, "gold": GOLD_EDGE}[tone]
    color = {"quiet": DIM, "live": COVERED, "gold": GOLD}[tone]
    dot = (
        f'<i style="width: 6px; height: 6px; border-radius: 9999px; background: {COVERED};"></i>'
        if tone == "live" else ""
    )
    return (
        f'<span style="display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px;'
        f' border: 1px solid {edge}; border-radius: 9999px; background: {RAISED};'
        f' font-family: {MONO}; font-size: 11px; letter-spacing: 0.04em; text-transform: uppercase;'
        f' color: {color};">{dot}{text}</span>'
    )


def badge(text, tone):
    edge, wash, color = {
        "met": (COVERED_EDGE, COVERED_WASH, COVERED),
        "single": (SINGLE_EDGE, SINGLE_WASH, SINGLE),
        "interp": (LINE_STRONG, RAISED, INTERP),
    }[tone]
    return (
        f'<span style="display: inline-flex; align-items: center; padding: 2px 8px;'
        f' border: 1px solid {edge}; border-radius: 9999px; background: {wash};'
        f' font-family: {MONO}; font-size: 10px; letter-spacing: 0.04em; text-transform: uppercase;'
        f' color: {color}; white-space: nowrap;">{text}</span>'
    )


def rail(active_note=""):
    """The board rail, slim, so the mockups keep the page's real proportions."""
    boards = [
        ("Crossing the Bitterroots — September 1805", "1805-09-09 → 1805-09-30", "3/5", "28", True),
        ("The Great Falls Portage — June and July 1805", "1805-06-01 → 1805-07-15", "4/5", "29", False),
        ("Lemhi Pass and the Shoshone — August 1805", "1805-08-01 → 1805-08-31", "3/6", "27", False),
        ("Descending the Columbia — October 1805", "1805-10-01 → 1805-10-31", "1/5", "20", False),
        ("Fort Clatsop Winter — December 1805 to March 1806", "1805-12-01 → 1806-03-31", "5/5", "50", False),
    ]
    rows = []
    for title, window, met, cites, current in boards:
        edge = GOLD_EDGE if current else LINE
        bg = RAISED if current else "transparent"
        rows.append(
            f'<div style="display: flex; flex-direction: column; gap: 4px; padding: 10px 11px;'
            f' border: 1px solid {edge}; border-radius: 4px; background: {bg};">'
            f'<span style="font-size: 12.5px; line-height: 1.35; color: {TEXT};">{esc(title)}</span>'
            f'<span class="mn" style="font-size: 10.5px; color: {DIMMER};">{window}</span>'
            f'<span class="mn" style="font-size: 10.5px; color: {DIMMER};">'
            f'<b style="color: {COVERED if met[0] == met[2] else GOLD}; font-weight: 500;">{met}</b> covered'
            f' · <b style="color: {DIM}; font-weight: 500;">{cites}</b> cites</span>'
            f"</div>"
        )
    return (
        f'<aside style="display: flex; flex-direction: column; gap: 12px; width: 248px;'
        f' padding: 16px 14px; border-right: 1px solid {LINE}; background: {PANEL};">'
        f'<div style="display: flex; align-items: center; gap: 8px;">'
        f'<span class="dp" style="font-size: 19px; color: {GOLD};">SourceCut</span>'
        f'<span class="lb" style="padding: 2px 6px; border: 1px solid {LINE_STRONG}; border-radius: 3px;">Archive</span>'
        f"</div>"
        f'<div style="padding: 9px 11px; border: 1px solid {GOLD_EDGE}; border-radius: 4px;'
        f' font-size: 12.5px; color: {GOLD};">+ New research board</div>'
        f'<div style="padding: 8px 11px; border: 1px solid {LINE}; border-radius: 4px;'
        f' background: {RECESSED}; font-size: 12.5px; color: {DIMMER};">Search boards…</div>'
        f'<p class="lb" style="margin-top: 4px;">Captured boards</p>'
        f'<div style="display: flex; flex-direction: column; gap: 7px;">{"".join(rows)}</div>'
        f'<div style="margin-top: auto; display: flex; flex-direction: column; gap: 8px;">'
        f"{active_note}{pill('ClickHouse MCP · read-only', 'live')}</div>"
        f"</aside>"
    )


def slate(trace=True):
    right = pill("Expedition range 18050909–18050930") + pill("Round 2 / 2") + pill("ClickHouse MCP · read-only", "live")
    if trace:
        right += pill("Execution trace 17", "gold")
    return (
        f'<header style="display: flex; align-items: center; justify-content: space-between;'
        f' gap: 16px; padding-bottom: 12px; border-bottom: 1px solid {LINE};">'
        f'<span class="lb">Captured board · bitterroot-september-1805</span>'
        f'<div style="display: flex; gap: 8px;">{right}</div>'
        f"</header>"
    )


def tabs(orientation="row"):
    items = []
    for index, (number, name, count, tone) in enumerate(TABS):
        active = index == 0
        dot = {"met": COVERED, "single": SINGLE}[tone]
        edge = GOLD if active else LINE
        bg = RAISED if active else PANEL
        color = TEXT if active else DIM
        count_edge, count_color = (
            (COVERED_EDGE, COVERED) if (active and tone == "met")
            else (SINGLE_EDGE, SINGLE) if tone == "single"
            else (LINE_STRONG, DIMMER)
        )
        grow = "width: 100%; flex-wrap: wrap;" if orientation == "column" else ""
        items.append(
            f'<div style="display: flex; align-items: center; gap: 8px; {grow}'
            f' padding: 7px 9px; border: 1px solid {edge}; border-radius: 4px; background: {bg};'
            f' font-family: {MONO}; font-size: 12px; color: {color}; white-space: nowrap;">'
            f'<i style="flex: none; width: 8px; height: 8px; border-radius: 9999px; background: {dot};"></i>'
            f'<span style="font-weight: 500;"><span style="color: {GOLD if active else DIMMER};">{number}</span> {name}</span>'
            f'<span style="margin-left: auto; padding: 1px 6px; border: 1px solid {count_edge};'
            f' border-radius: 3px; background: {RECESSED}; font-size: 10px; color: {count_color};">{count}</span>'
            f"</div>"
        )
    if orientation == "column":
        return f'<div style="display: flex; flex-direction: column; gap: 6px;">{"".join(items)}</div>'
    return (
        f'<div style="display: flex; align-items: center; gap: 12px; padding: 6px;'
        f' {RECESS_BOX}">'
        f'<span class="lb" style="flex: none; padding: 5px 9px; border: 1px solid {LINE};'
        f' border-radius: 4px; background: {PANEL}; color: {GOLD};">Requirements</span>'
        f'<div style="display: flex; gap: 6px;">{"".join(items)}</div>'
        f"</div>"
    )


def timeline(height=64, show_route=True, show_axis=True):
    """The three bands over one date axis, at the real per-day states."""
    cells = []
    for date, citations, corroborated, state in DAYS:
        fill = round(corroborated / 5 * 100)
        colour = STATE_FILL[state]
        cells.append(
            f'<i style="display: block; height: 100%;'
            f' background: linear-gradient(to top, {colour} {fill}%, {M_SILENT} {fill}%);"></i>'
        )
    strip = (
        f'<div style="display: grid; grid-template-columns: repeat(22, 1fr); gap: 1px;'
        f' height: 22px; padding: 0 1px; border-top: 1px solid {LINE}; background: {LINE};">'
        f'{"".join(cells)}</div>'
    )

    route = ""
    if show_route:
        blocks = []
        for name, _date, _lon, _lat, _count, start, length in WAYPOINTS:
            active = start <= HELD < start + length
            left = start / 22 * 100
            width = length / 22 * 100
            label = name if length / 22 >= 0.05 else ""
            blocks.append(
                f'<div style="position: absolute; top: 0; bottom: 0; left: {left:.2f}%;'
                f' width: {width:.2f}%; display: flex; align-items: center; overflow: hidden;'
                f' padding: 0 5px; border-left: 1px solid {LINE_STRONG};'
                f' background: {GOLD_WASH if active else "transparent"};'
                f' font-family: {MONO}; font-size: 10px; white-space: nowrap;'
                f' text-overflow: ellipsis; color: {GOLD if active else DIM};">{esc(label)}</div>'
            )
        route = (
            f'<div style="position: relative; height: 24px; border-top: 1px solid {LINE};">'
            f'{"".join(blocks)}</div>'
        )

    axis = ""
    if show_axis:
        ticks = []
        for index in (0, 3, 6, 9, 12, 15, 18, 21):
            label = "Sep 09" if index == 0 else f"{9 + index:02d}"
            left = (index + 0.5) / 22 * 100
            if index == 0:
                position, transform, border = "left: 0;", "", "border-left: 0;"
            elif index == 21:
                position, transform, border = f"left: {left:.2f}%;", "transform: translateX(-100%);", ""
            else:
                position, transform, border = f"left: {left:.2f}%;", "transform: translateX(-50%);", ""
            ticks.append(
                f'<span class="mn" style="position: absolute; top: 0; {position} {transform}'
                f' padding: 4px 0 0 4px; {border} border-left: 1px solid {LINE_STRONG};'
                f' font-size: 10px; line-height: 1; color: {GOLD if index == 0 else DIMMER};">{label}</span>'
            )
        axis = (
            f'<div style="position: relative; height: 20px; border-top: 1px solid {LINE};'
            f' background: {PANEL};">{"".join(ticks)}</div>'
        )

    playhead = (
        f'<div style="position: absolute; top: 0; bottom: 0; left: {(HELD + 0.5) / 22 * 100:.2f}%;'
        f' width: 1px; background: {GOLD}; box-shadow: 0 0 6px {GOLD}; z-index: 3;"></div>'
    )

    return (
        f'<div style="position: relative; overflow: hidden; {RECESS_BOX}">'
        f"{playhead}"
        f'<div style="position: relative; height: {height}px;">'
        f'<svg viewBox="0 0 1000 64" preserveAspectRatio="none" style="display: block; width: 100%; height: 100%;">'
        f'<polygon points="0,64 {CURVE} 1000,64" fill="{GOLD_WASH}"></polygon>'
        f'<polyline points="{CURVE}" fill="none" stroke="{GOLD}" stroke-width="1.5" vector-effect="non-scaling-stroke"></polyline>'
        f"</svg>"
        f'<span class="lb" style="position: absolute; top: 6px; right: 10px;">Citations per day · peak 6</span>'
        f"</div>{strip}{route}{axis}</div>"
    )


def route_plot(width, height, labels="all"):
    """The waypoint plot, fitted to the waypoints it has."""
    pad_x, pad_y = (68, 34) if labels == "all" else (26, 20)
    lons = [point[2] for point in WAYPOINTS]
    lats = [point[3] for point in WAYPOINTS]
    west, east = min(lons), max(lons)
    south, north = min(lats), max(lats)
    placed = []
    for index, (name, _date, lon, lat, count, start, length) in enumerate(WAYPOINTS):
        x = pad_x + (lon - west) / (east - west) * (width - pad_x * 2)
        y = pad_y + (north - lat) / (north - south) * (height - pad_y * 2)
        placed.append((name, x, y, count, start <= HELD < start + length))
    line = " ".join(f"{x:.1f},{y:.1f}" for _n, x, y, _c, _a in placed)
    dots = []
    for index, (name, x, y, count, active) in enumerate(placed):
        radius = 4 + min(count, 7)
        fill = GOLD_BRIGHT if active else DIM
        dots.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{fill}"'
            f' stroke="{GROUND}" stroke-width="1.5"></circle>'
        )
        if labels == "all" or (labels == "active" and active):
            near = x > width * 0.72
            above = index % 2 == 0
            dots.append(
                f'<text x="{x + (-12 if near else 12):.1f}" y="{y + (-13 if above else 21):.1f}"'
                f' text-anchor="{"end" if near else "start"}" fill="{GOLD if active else DIM}"'
                f' font-family="{MONO}" font-size="11">{esc(name)}</text>'
            )
    return (
        f'<svg viewBox="0 0 {width} {height}" style="display: block; width: 100%; height: auto;'
        f' aspect-ratio: {width} / {height}; {RECESS_BOX}">'
        f'<polyline points="{line}" fill="none" stroke="{GOLD_DEEP}" stroke-width="1.5"'
        f' stroke-dasharray="5 6"></polyline>{"".join(dots)}</svg>'
    )


def scrub_bar():
    step = (
        f'<span style="display: inline-flex; align-items: center; justify-content: center;'
        f' width: 26px; height: 26px; border: 1px solid {LINE_STRONG}; border-radius: 4px;'
        f' background: {RAISED}; color: {DIM}; font-size: 14px; line-height: 1;">%s</span>'
    )
    return (
        f'<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 8px 16px;'
        f' padding: 8px 10px; {PANEL_BOX}">'
        f'<div style="display: flex; align-items: center; gap: 6px;">'
        f"{step % '‹'}"
        f'<span class="mn" style="min-width: 96px; text-align: center; font-size: 11px; color: {DIMMER};">day 11 of 22</span>'
        f"{step % '›'}</div>"
        f'<span class="mn" style="font-size: 15px; color: {TEXT};">1805–09–19</span>'
        f'<span class="mn" style="font-size: 10px; letter-spacing: 0.06em; text-transform: uppercase; color: {GOLD};">5 of 5 corroborated</span>'
        f'<span style="font-size: 12.5px; color: {DIM};">2 citations · 3 authors writing · Bitterroot Ridge</span>'
        f'<span class="lb" style="margin-left: auto; padding: 5px 9px; border: 1px solid {LINE_STRONG};'
        f' border-radius: 4px; background: {RAISED}; color: {DIM};">Release date</span>'
        f"</div>"
    )


def panel(title, meta, body, pad="12px 14px", extra=""):
    return (
        f'<section style="display: flex; flex-direction: column; min-width: 0; {PANEL_BOX}'
        f" padding: {pad}; {extra}\">"
        f'<div style="display: flex; align-items: baseline; justify-content: space-between;'
        f' gap: 10px; margin-bottom: 10px;">'
        f'<h3 class="dp" style="font-size: 16px; color: {TEXT};">{title}</h3>'
        f'<span class="lb">{meta}</span></div>{body}</section>'
    )


def quotes(count=3):
    cards = []
    for text, author, date, passage in QUOTES[:count]:
        cards.append(
            f'<blockquote style="margin: 0; padding: 11px 13px; border: 1px solid {LINE};'
            f' border-left: 2px solid {GOLD_EDGE}; border-radius: 4px; background: {RECESSED};">'
            f'<span class="dp" style="display: block; font-style: italic; font-size: 14px;'
            f' line-height: 1.5; color: {TEXT};">“{esc(text)}”</span>'
            f'<cite style="display: flex; flex-wrap: wrap; gap: 4px 10px; margin-top: 9px;'
            f' font-style: normal; font-family: {MONO}; font-size: 10px; color: {DIMMER};">'
            f'<b style="font-weight: 500; color: {DIM};">{author}</b><span>{date}</span>'
            f'<span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{passage}</span>'
            f"</cite></blockquote>"
        )
    return f'<div style="display: flex; flex-direction: column; gap: 8px;">{"".join(cards)}</div>'


def matrix():
    rows = []
    for author, states in AGREEMENT.items():
        cells = []
        for index, mark in enumerate(states):
            colour = {"M": M_ACTIVE, "s": M_SILENT, ".": M_ABSENT}[mark]
            edge = f"box-shadow: inset 0 0 0 1px {LINE};" if mark == "." else ""
            ring = f"outline: 1px solid {GOLD};" if index == HELD else ""
            cells.append(
                f'<i style="display: block; height: 15px; border-radius: 2px;'
                f' background: {colour}; {edge}{ring}"></i>'
            )
        rows.append(
            f'<div style="display: contents;">'
            f'<span class="mn" style="font-size: 10.5px; color: {DIM}; white-space: nowrap;">{author.split()[-1]}</span>'
            f'<div style="display: grid; grid-template-columns: repeat(22, 1fr); gap: 2px;">{"".join(cells)}</div>'
            f"</div>"
        )
    legend = (
        f'<div style="display: flex; flex-wrap: wrap; gap: 4px 12px; margin-top: 9px;'
        f' font-family: {MONO}; font-size: 10px; color: {DIMMER};">'
        f'<span><i style="display: inline-block; width: 9px; height: 9px; border-radius: 2px;'
        f' background: {M_ACTIVE}; vertical-align: -1px;"></i> mentions the topic</span>'
        f'<span><i style="display: inline-block; width: 9px; height: 9px; border-radius: 2px;'
        f' background: {M_SILENT}; vertical-align: -1px;"></i> wrote that day, silent on it</span>'
        f'<span><i style="display: inline-block; width: 9px; height: 9px; border-radius: 2px;'
        f' background: {M_ABSENT}; box-shadow: inset 0 0 0 1px {LINE}; vertical-align: -1px;"></i> no entry</span>'
        f"</div>"
    )
    return (
        f'<div style="display: grid; grid-template-columns: auto minmax(0, 1fr);'
        f' gap: 5px 9px; align-items: center;">{"".join(rows)}</div>{legend}'
    )


def references(count=3, thumb_height=52):
    cards = []
    for confidence, asset_id, meta, title in REFERENCES[:count]:
        tone = {"HIGH": "met", "INTERPRETIVE": "interp", "UNSUPPORTED": "interp"}[confidence]
        cards.append(
            f'<div style="display: grid; grid-template-columns: 62px minmax(0, 1fr); gap: 10px;'
            f' padding: 9px 10px; border: 1px solid {LINE}; border-radius: 4px; background: {RECESSED};">'
            f'<div style="display: flex; align-items: center; justify-content: center;'
            f' height: {thumb_height}px; border: 1px solid {LINE}; border-radius: 3px;'
            f' background: {RAISED}; font-family: {MONO}; font-size: 9px; color: {DIMMER};">{asset_id.split(":")[1][:7]}</div>'
            f'<div style="display: flex; flex-direction: column; gap: 4px; min-width: 0;">'
            f'<div style="display: flex; align-items: center; gap: 7px;">{badge(confidence, tone)}'
            f'<span class="mn" style="font-size: 10px; color: {DIMMER};">{asset_id}</span></div>'
            f'<span style="font-size: 12.5px; line-height: 1.35; color: {TEXT};">{esc(title)}</span>'
            f'<span class="mn" style="font-size: 10px; color: {DIMMER};">{meta}</span>'
            f"</div></div>"
        )
    return f'<div style="display: flex; flex-direction: column; gap: 8px;">{"".join(cards)}</div>'


def stat_block():
    return (
        f'<div style="display: flex; flex-direction: column; gap: 8px; padding: 12px 14px;'
        f' {PANEL_BOX}">'
        f'<div style="display: flex; align-items: baseline; gap: 8px;">'
        f'<span class="dp" style="font-size: 34px; line-height: 1; color: {TEXT};">3</span>'
        f'<span class="dp" style="font-size: 20px; color: {DIMMER};">/ 5</span>'
        f'<span class="lb" style="max-width: 96px; line-height: 1.25;">Requirements defended</span>'
        f"</div>"
        f'<div style="display: flex; flex-wrap: wrap; gap: 6px;">{badge("3 covered", "met")}{badge("2 single-author", "single")}</div>'
        f'<div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px 12px;'
        f' font-family: {MONO}; font-size: 10.5px; color: {DIMMER};">'
        f'<span>Corpus<br><b style="color: {DIM}; font-weight: 500;">Gutenberg 8419</b></span>'
        f'<span>Catalog<br><b style="color: {DIM}; font-weight: 500;">Library of Congress</b></span>'
        f'<span>Rounds<br><b style="color: {DIM}; font-weight: 500;">2</b></span>'
        f'<span>Interpretive<br><b style="color: {DIM}; font-weight: 500;">8 references</b></span>'
        f"</div></div>"
    )


def brief(compact=True):
    return (
        f'<div style="display: flex; flex-direction: column; gap: 7px; min-width: 0;">'
        f'<span class="lb lb-gold">Production research brief · bitterroot-september-1805</span>'
        f'<h1 class="dp" style="font-size: 30px; line-height: 1.14; letter-spacing: -0.02em; color: {TEXT};">'
        f"Crossing the Bitterroots — September 1805</h1>"
        f'<p style="max-width: 62ch; font-size: 13px; line-height: 1.55; color: {DIM};">'
        f"Evidence-derived board with 5 requirements, 15 selected asset references, and exact "
        f"passage drill-down. 3 of 5 planned requirements met their evidence criteria after 2 "
        f"research rounds.</p>"
        f'<div style="display: flex; flex-wrap: wrap; gap: 6px 16px; font-family: {MONO};'
        f' font-size: 10.5px; color: {DIMMER};">'
        f'<span><b style="color: {GOLD}; font-weight: 500;">28</b> passages cited</span>'
        f'<span><b style="color: {GOLD}; font-weight: 500;">25</b> references reviewed</span>'
        f'<span><b style="color: {GOLD}; font-weight: 500;">9</b> waypoints</span>'
        f"<span>planner · gemini:gemini-2.5-flash</span></div></div>"
    )


def focus_line():
    return (
        f'<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 8px 14px;">'
        f'<span class="lb">Active focus</span>'
        f'<b class="dp" style="font-size: 17px; color: {GOLD}; text-decoration: underline;'
        f' text-underline-offset: 3px; font-weight: 400;">Mountainous Terrain and Trail Conditions</b>'
        f"{badge('Covered', 'met')}"
        f'<span class="lb" style="padding: 5px 9px; border: 1px solid {LINE_STRONG};'
        f' border-radius: 4px; background: {RAISED}; color: {DIM};">Create previs ↗</span>'
        f'<span class="lb" style="margin-left: auto;">3 authors · 19 days · 12 cites</span>'
        f"</div>"
    )


def footer():
    return (
        f'<footer style="display: flex; flex-wrap: wrap; align-items: center; gap: 8px 18px;'
        f' padding-top: 11px; border-top: 1px solid {LINE}; font-family: {MONO};'
        f' font-size: 10.5px; color: {DIMMER};">'
        f"<span>Journals · Gutenberg 8419</span><span>References · Library of Congress</span>"
        f"<span>8 references marked interpretive</span>"
        f'<span style="margin-left: auto; color: {GOLD};">1 candidate unsupported · 1 asset excluded by rights ↗</span>'
        f"</footer>"
    )


def shell(inner, rail_note=""):
    return (
        f'<div style="display: flex; min-height: 100%; background: {GROUND};">'
        f"{rail(rail_note)}"
        f'<main style="flex: 1; min-width: 0; display: flex; flex-direction: column;'
        f' gap: 14px; padding: 16px 20px 20px;">{inner}</main></div>'
    )


# ── A · the instrument bench ────────────────────────────────────────────
def main_artboard():
    instrument = (
        f'<section style="display: flex; flex-direction: column; gap: 10px; {PANEL_BOX} padding: 12px 14px;">'
        f'<div style="display: flex; align-items: baseline; justify-content: space-between; gap: 12px;">'
        f'<div style="display: flex; align-items: baseline; gap: 10px;">'
        f'<h3 class="dp" style="font-size: 16px; color: {TEXT};">When, and where</h3>'
        f'<span class="lb">One clock · the panels below follow it</span></div>'
        f'<span class="lb"><b style="color: {GOLD}; font-weight: 500;">6 of 22</b> days corroborate all 5</span>'
        f"</div>"
        f'<div style="display: grid; grid-template-columns: minmax(0, 1.62fr) minmax(0, 1fr);'
        f' gap: 12px; align-items: stretch;">'
        f'<div style="display: flex; flex-direction: column; gap: 6px; min-width: 0;">'
        f"{timeline(height=58)}"
        f'<span class="lb">Record density · citations, corroboration and the waypoint in force</span></div>'
        f'<div style="display: flex; flex-direction: column; gap: 6px; min-width: 0;">'
        f"{route_plot(430, 158, labels="active")}"
        f'<span class="lb">Route reference · modern NPS positions, cited per waypoint</span></div>'
        f"</div>{scrub_bar()}</section>"
    )

    workbench = (
        f'<div style="display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(0, 1.02fr)'
        f' minmax(0, 1.06fr); gap: 12px; align-items: start;">'
        f"{panel('Verbatim journal extracts', '12 cites · sorted to the held day', quotes(3))}"
        f"{panel('Who wrote it down, and when', 'Sep 09 – 30 · 3 authors', matrix() + criterion())}"
        f"{panel('Correlated archival references', '5 matched · 3 shown', references(3))}"
        f"</div>"
    )

    inner = (
        f"{slate()}"
        f'<div style="display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: 16px;'
        f' align-items: start;">{brief()}{stat_block()}</div>'
        f"{tabs()}{focus_line()}{instrument}{workbench}{footer()}"
    )
    return head("Instrument bench") + shell(inner) + TAIL


def criterion():
    return (
        f'<div style="margin-top: 11px; padding: 9px 11px; border: 1px solid {LINE};'
        f' border-left: 2px solid {COVERED_EDGE}; border-radius: 4px; background: {RECESSED};">'
        f'<span class="lb" style="color: {COVERED};">Criterion met</span>'
        f'<p style="margin-top: 5px; font-size: 12px; line-height: 1.5; color: {DIM};">'
        f"Passages describing the physical characteristics of the mountains, the trail and its "
        f"obstacles, from at least 2 authors.</p></div>"
    )


# ── B · the reading room ────────────────────────────────────────────────
def vertical_timeline():
    rows = []
    for index, (date, citations, corroborated, state) in enumerate(DAYS):
        held = index == HELD
        width = round(citations / PEAK * 100)
        colour = STATE_FILL[state]
        rows.append(
            f'<div style="display: grid; grid-template-columns: 46px minmax(0, 1fr) 26px;'
            f' gap: 7px; align-items: center; padding: 1px 4px; border-radius: 3px;'
            f' background: {GOLD_WASH if held else "transparent"};">'
            f'<span class="mn" style="font-size: 10px; color: {GOLD if held else DIMMER};">'
            f'{"Sep " + str(date)[6:] if index in (0, 21) else str(date)[6:]}</span>'
            f'<div style="position: relative; height: 11px; border-radius: 2px; background: {M_SILENT};">'
            f'<div style="position: absolute; inset: 0 auto 0 0; width: {width}%;'
            f' border-radius: 2px; background: {colour};"></div></div>'
            f'<span class="mn" style="font-size: 9.5px; text-align: right; color: {DIMMER};">{corroborated}/5</span>'
            f"</div>"
        )
    return f'<div style="display: flex; flex-direction: column; gap: 2px;">{"".join(rows)}</div>'


def waypoint_list():
    rows = []
    for name, date, _lon, _lat, count, start, length in WAYPOINTS:
        active = start <= HELD < start + length
        rows.append(
            f'<div style="display: flex; align-items: center; gap: 8px; padding: 4px 6px;'
            f' border-radius: 3px; background: {GOLD_WASH if active else "transparent"};">'
            f'<i style="flex: none; width: 6px; height: 6px; border-radius: 9999px;'
            f' background: {GOLD_BRIGHT if active else DIM};"></i>'
            f'<span style="flex: 1; font-size: 12px; color: {GOLD if active else DIM};">{esc(name)}</span>'
            f'<span class="mn" style="font-size: 10px; color: {DIMMER};">{str(date)[4:6]}–{str(date)[6:]} · {count}</span>'
            f"</div>"
        )
    return f'<div style="display: flex; flex-direction: column; gap: 1px;">{"".join(rows)}</div>'


def direction_b():
    tab_rail = (
        f'<aside style="display: flex; flex-direction: column; gap: 10px; width: 218px;'
        f' flex: none; padding: 12px; {PANEL_BOX}">'
        f'<span class="lb lb-gold">Requirements</span>{tabs("column")}'
        f'<div style="margin-top: 4px; padding-top: 10px; border-top: 1px solid {LINE};">'
        f'<span class="lb">Round 2 · widened</span>'
        f'<div style="display: flex; flex-wrap: wrap; gap: 4px; margin-top: 7px;">'
        + "".join(
            f'<span class="mn" style="padding: 2px 6px; border: 1px solid {LINE_STRONG};'
            f' border-radius: 9999px; background: {RAISED}; font-size: 9.5px; color: {DIMMER};">{term}</span>'
            for term in ("mountains", "road", "route", "ruged", "creek", "snowing", "rained", "wet")
        )
        + "</div></div></aside>"
    )

    context = (
        f'<aside style="display: flex; flex-direction: column; gap: 12px; width: 348px;'
        f' flex: none;">'
        f"{stat_block()}"
        f"{panel('Record density', '6 of 22 full', vertical_timeline(), pad='11px 12px')}"
        f"{panel('Route reference', '9 waypoints', route_plot(330, 150, labels="active") + '<div style=\"margin-top: 9px;\">' + waypoint_list() + '</div>', pad='11px 12px')}"
        f"</aside>"
    )

    evidence = (
        f'<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 12px;">'
        f"{focus_line()}"
        f"{panel('Verbatim journal extracts', '12 cites · 3 corroborating authors · 19 days', quotes(3))}"
        f"{panel('Who wrote it down, and when', 'Sep 09 – 30', matrix() + criterion())}"
        f"{panel('Correlated archival references', '5 matched', references(2, thumb_height=46))}"
        f"</div>"
    )

    inner = (
        f"{slate()}"
        f'<div style="display: flex; gap: 16px; align-items: start;">{brief()}</div>'
        f'<div style="display: flex; gap: 14px; align-items: stretch;">{tab_rail}{evidence}{context}</div>'
        f"{footer()}"
    )
    return head("Reading room") + shell(inner) + TAIL


# ── C · survey, then drill ──────────────────────────────────────────────
def direction_c():
    survey = (
        f'<div style="display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr)'
        f' minmax(0, 1fr); gap: 12px; align-items: stretch;">'
        f"{panel('The brief', 'bitterroot-september-1805', brief_body(), pad='12px 14px')}"
        f"{panel('Route reference', '9 waypoints · NPS positions', route_plot(400, 196, labels="active") + waypoint_strip(), pad='12px 14px')}"
        f"{panel('Correlated archival references', '25 reviewed · 8 interpretive', references(3, thumb_height=44), pad='12px 14px')}"
        f"</div>"
    )

    drill = (
        f'<section style="display: flex; flex-direction: column; gap: 12px; {PANEL_BOX}'
        f' padding: 14px 16px; border-color: {GOLD_EDGE};">'
        f"{focus_line()}"
        f'<div style="display: grid; grid-template-columns: minmax(0, 1.42fr) minmax(0, 1fr);'
        f' gap: 14px; align-items: start;">'
        f'<div style="min-width: 0;"><span class="lb" style="display: block; margin-bottom: 8px;">'
        f"Verbatim journal extracts · 12 cites</span>{quotes(3)}</div>"
        f'<div style="min-width: 0;"><span class="lb" style="display: block; margin-bottom: 8px;">'
        f"Who wrote it down, and when · Sep 09 – 30</span>{matrix()}{criterion()}</div>"
        f"</div></section>"
    )

    inner = (
        f"{slate()}"
        f'<section style="display: flex; flex-direction: column; gap: 9px; {PANEL_BOX} padding: 12px 14px;">'
        f'<div style="display: flex; align-items: baseline; justify-content: space-between; gap: 12px;">'
        f'<div style="display: flex; align-items: baseline; gap: 10px;">'
        f'<h3 class="dp" style="font-size: 16px; color: {TEXT};">Record density</h3>'
        f'<span class="lb">The board\'s clock — every panel below reads the held day</span></div>'
        f'<span class="lb"><b style="color: {GOLD}; font-weight: 500;">6 of 22</b> days corroborate all 5</span></div>'
        f"{timeline(height=76)}{scrub_bar()}</section>"
        f"{survey}{tabs()}{drill}{footer()}"
    )
    return head("Survey then drill") + shell(inner) + TAIL


def brief_body():
    return (
        f'<div style="display: flex; flex-direction: column; gap: 9px;">'
        f'<h2 class="dp" style="font-size: 22px; line-height: 1.2; color: {TEXT};">'
        f"Crossing the Bitterroots — September 1805</h2>"
        f'<p style="font-size: 12.5px; line-height: 1.55; color: {DIM};">'
        f"Evidence-derived board with 5 requirements, 15 selected asset references, and exact "
        f"passage drill-down.</p>"
        f'<div style="display: flex; align-items: baseline; gap: 8px;">'
        f'<span class="dp" style="font-size: 30px; line-height: 1; color: {TEXT};">3</span>'
        f'<span class="dp" style="font-size: 18px; color: {DIMMER};">/ 5</span>'
        f'<span class="lb" style="max-width: 92px; line-height: 1.25;">Requirements defended</span></div>'
        f'<div style="display: flex; flex-wrap: wrap; gap: 6px;">{badge("3 covered", "met")}{badge("2 single-author", "single")}</div>'
        f'<div style="display: flex; flex-wrap: wrap; gap: 5px 14px; font-family: {MONO};'
        f' font-size: 10.5px; color: {DIMMER};">'
        f'<span><b style="color: {GOLD}; font-weight: 500;">28</b> passages cited</span>'
        f'<span><b style="color: {GOLD}; font-weight: 500;">25</b> references reviewed</span>'
        f"<span>2 rounds</span></div></div>"
    )


def waypoint_strip():
    chips = []
    for name, _date, _lon, _lat, _count, start, length in WAYPOINTS:
        active = start <= HELD < start + length
        chips.append(
            f'<span class="mn" style="padding: 2px 7px; border: 1px solid'
            f' {GOLD_EDGE if active else LINE_STRONG}; border-radius: 9999px;'
            f' background: {GOLD_WASH if active else RAISED}; font-size: 9.5px;'
            f' color: {GOLD if active else DIMMER};">{esc(name)}</span>'
        )
    return (
        f'<div style="display: flex; flex-wrap: wrap; gap: 5px; margin-top: 10px;">{"".join(chips)}</div>'
    )


# C was chosen, so it is the entry artboard; A and B keep their identities and
# move to a second page rather than being thrown away.
(OUT / "Main.dc.html").write_text(direction_c())
(OUT / "InstrumentBench.dc.html").write_text(main_artboard())
(OUT / "ReadingRoom.dc.html").write_text(direction_b())
(OUT / "SurveyThenDrill.dc.html").unlink(missing_ok=True)

canvas = {
    "pages": [
        {"id": "page-1", "name": "Chosen"},
        {"id": "page-2", "name": "Alternates"},
    ],
    "artboards": [
        {"file": "Main.dc.html", "x": 0, "y": 0, "w": 1440, "h": 1340,
         "title": "C \u00b7 Survey then drill", "expand": "fit", "page": "page-1"},
        {"file": "InstrumentBench.dc.html", "x": 0, "y": 0, "w": 1440, "h": 1220,
         "title": "A \u00b7 Instrument bench", "expand": "fit", "page": "page-2"},
        {"file": "ReadingRoom.dc.html", "x": 1560, "y": 0, "w": 1440, "h": 1470,
         "title": "B \u00b7 Reading room", "expand": "fit", "page": "page-2"},
    ],
    "annotations": [
        {"id": "note-c", "x": 0, "y": -170, "w": 620, "page": "page-1",
         "text": "C \u00b7 Survey then drill \u2014 chosen\n\nThe board reads as an overview "
                 "first: the clock full width, then brief, route and references as three equal "
                 "cards. The selected requirement opens as one gold-edged workbench below.\n\n"
                 "Known tradeoff: the evidence starts below the fold. Worth watching once this "
                 "is in code \u2014 if it bites, the survey row is the part to shrink."},
        {"id": "note-a", "x": 0, "y": -190, "w": 460, "page": "page-2",
         "text": "A \u00b7 Instrument bench \u2014 not chosen\n\nThe timeline and the route as "
                 "one pinned clock above three parallel evidence columns.\n\nTradeoff: dense. "
                 "The route map shrinks to a 430px inset and its labels go with it."},
        {"id": "note-b", "x": 1560, "y": -190, "w": 460, "page": "page-2",
         "text": "B \u00b7 Reading room \u2014 not chosen\n\nThree rails: requirements left, "
                 "evidence at full reading width, a context column right that never scrolls "
                 "away.\n\nTradeoff: four rails of chrome, and a vertical timeline loses the "
                 "shape of the record at a glance."},
    ],
    "launch": {"view": "canvas", "page": "page-1"},
}
(OUT / "canvas.json").write_text(json.dumps(canvas, indent=2))
print("wrote", *(p.name for p in sorted(OUT.glob("*.dc.html"))), "canvas.json")
