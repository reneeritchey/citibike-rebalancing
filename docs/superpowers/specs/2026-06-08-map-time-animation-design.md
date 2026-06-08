# Map Time Animation ("Watch the Day") Design

**Date:** 2026-06-08
**Status:** Approved design — ready for implementation planning
**Type:** Feature addition to the citibike-rebalancing Streamlit app

## Goal

Let the user **animate the map through the course of a day** so they can watch
Citi Bike imbalance build and shift across the city. A Play/Pause control
auto-advances the hour; the map's 3D columns morph frame-by-frame while the
camera stays fixed.

## Scope

- **In scope:** a Play/Pause + loop animation that advances the existing
  hour-of-day value 0→23 and re-renders the map each step; a manual scrubber;
  relocating the hour control to a playback row above the map.
- **Out of scope (YAGNI):** speed control, user-selected time range, per-hour
  (non-cumulative) mode, GIF/video export, true GPU/client-side animation.

## What each frame shows

**Cumulative imbalance.** Each frame shows net displacement accumulated since
12am — `cumulative_drift(view, up_to_hour=hour)`, the same model the current
slider uses. The animation makes imbalance visibly accumulate toward rush hours
and reset as the loop restarts. (Confirmed over per-hour flux during design.)

## Approach

**Server-driven rerun loop** (chosen over a custom GPU component or a
pre-rendered video, both of which would break live interactivity or require
heavy new tooling). Streamlit reruns the whole script per frame; this fits the
existing architecture, reuses `cumulative_drift()`, keeps all filters and
zoom-to-station working live, and holds the camera steady. Trade-off: ~1
frame/second "stop-motion" (full day ≈ 14s), not 60fps — acceptable for a
24-step day.

## UX

A **time-playback row directly above the map** (main pane), co-located with the
animation it drives. The sidebar keeps the categorical filters (day type, rider,
minimum trips, station picker).

Layout via `st.columns([1, 2, 6])`:

```
[ ▶ Play ]   Hour: 08:00   [──────●────────────────]   (0 … 23 scrubber)
```

- **▶ Play / ⏸ Pause** toggle button.
- Live **"Hour: HH:00"** readout.
- The existing **slider as a manual scrubber** — dragging jumps to any hour and
  **pauses** playback.

The hour slider moves out of the sidebar into this row.

## State model (`st.session_state`)

Two values are the single source of truth:

- `playing: bool` — default `False`.
- `hour: int` (0–23) — default `9`.

The slider is rendered with `value=st.session_state.hour` and **no widget key**,
so the animation loop can mutate `hour` without triggering Streamlit's
"cannot modify a widget-instantiated value" error. Reconciliation each run:

- If the slider's returned value differs from `st.session_state.hour`, the user
  scrubbed → set `hour` to the slider value and set `playing = False`.

## Loop mechanics

1. Initialize `hour` and `playing` in session state if absent.
2. Render the playback row; the Play/Pause button toggles `playing`.
3. Reconcile the scrubber (above).
4. Render the map and charts from `cumulative_drift(view, up_to_hour=hour)`
   (unchanged logic). The deck `key` (`deck-{selected_name}`) already excludes
   the hour, so the camera stays fixed and only the columns change.
5. At the **bottom** of the script, if `playing`:
   `time.sleep(SPEED)` → `hour = next_hour(hour)` → `st.rerun()`.

`SPEED ≈ 0.6` seconds/frame. `next_hour` wraps 23→0 so playback loops.

## Code structure

- All UI/loop changes live in **`app/streamlit_app.py`**. No changes to the
  analysis pipeline.
- One tiny pure, unit-tested helper in **`src/metrics.py`**:
  `next_hour(h: int) -> int` returns `(h + 1) % 24`. Keeps the loop's advance
  logic testable rather than an inline expression.

## Edge cases & error handling

- **Empty filter result while playing:** before the existing
  `st.warning(...)` + `st.stop()`, set `playing = False` so playback pauses
  cleanly with the warning instead of appearing hung.
- **Selecting a station mid-animation:** the deck `key` changes → the map flies
  to the station, then animation continues from there. Acceptable.
- **Performance:** each frame re-reads the `@st.cache_data` parquet (cached) and
  recomputes `cumulative_drift` over ~2k stations (cheap). Cadence is dominated
  by Streamlit's rerun, not compute.
- **Rapid Play/Pause clicks:** harmless; the toggle flips `playing`.
- **`time.sleep` blocks the session thread during playback** — expected for this
  pattern; affects only the animating session.

## Testing

- **TDD** `next_hour`: `next_hour(0) == 1`, `next_hour(23) == 0`.
- **Manual + Playwright verification:** click Play, capture two frames a couple
  seconds apart, assert the map region changed and the "Hour" readout advanced;
  click Pause, assert the hour stops advancing; scrub the slider, assert
  playback paused.
- Existing 14 tests must stay green.

## Success criteria

- Pressing Play animates the map through hours 0→23 and loops, with the camera
  fixed and columns morphing to show cumulative imbalance.
- Pause stops playback; the scrubber still works and pauses playback when used.
- All existing filters and zoom-to-station continue to work during playback.
