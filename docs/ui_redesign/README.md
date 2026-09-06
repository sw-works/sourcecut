# UI redesign

How the current interface was arrived at. These are working artifacts, kept
because they record decisions the shipped code cannot explain on its own.

| Directory | What it is |
|---|---|
| `sourcecut_archival_os/DESIGN.md` | The design system the shipped CSS follows: palette, type, the meaning of each confidence colour. Normative — `apps/web/src/styles/sourcecut.css` implements it. |
| `sourcecut_new_scene_research_landing/` | The landing-page direction, as exported from the design tool. |
| `sourcecut_workstation_with_board_sidebar/` | The workspace direction: one board at a time, every other board in a rail. |
| `board_layout/` | Three layouts for the board itself — an instrument bench, a reading room, and survey-then-drill. The third was built. |

The two exported mockups predate later product decisions and are not a
description of the current app: the previsualisation control they show was
built and then removed in full (`tasks/013`). Read them as the design argument
they were, and the running app as the answer.
