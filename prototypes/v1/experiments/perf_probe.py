"""Performance harness for the Praatao hover coach.

What it measures (all on this machine, with a live Praat)
-----------------------------------------------------------

1. **Sensing cost** - how long one call of every hot function takes:
   the UIA hit test, the tree walk, the knowledge base lookup, the fast
   state probe, the canvas grab, and the cheap Win32 helpers.
2. **Pipeline cost** - how long the tutor needs to turn a control into
   advice text, and how long the card needs to draw itself.
3. **End-to-end latency** - from "the pointer comes to rest on a control"
   to "the card is on screen", broken into the parts:
   poll granularity, dwell, hit test, KB lookup, advice building, card render.
4. **CPU load** - the CPU time and the wall time of the coach process
   while the mouse is idle for 20 s, and while the mouse sweeps over Praat
   for 20 s.
5. **False triggers** - how often the card appears for a control the
   pointer merely swept over.

Every number is a median and a 95th percentile over at least 20 runs
(``time.perf_counter`` throughout).  The result is printed as a table and
written to ``perf_baseline.json``.

Usage::

    python prototypes/v1/experiments/perf_probe.py
    python prototypes/v1/experiments/perf_probe.py --out perf_baseline.json
    python prototypes/v1/experiments/perf_probe.py --quick   # fewer runs
    python prototypes/v1/experiments/perf_probe.py --legacy  # the old code

With ``--legacy`` the harness puts the implementations of *before* the
performance work back (the old hit test, the old knowledge base scan, the
old drawing-area lookup, the old menu check, ...) and measures them with
exactly the same code.  That is what makes the before-and-after table in
``docs/15-performance.md`` comparable.

The harness moves the mouse.  The original mouse position is restored when
it is done.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from praatao.sensors.praat_state import PraatStateProbe  # noqa: E402
from praatao.sensors.uia import (  # noqa: E402
    PraatUI,
    _menu_popup_open,
    praat_has_focus,
)
from praatao.tutor.kb import load_default, normalize_key  # noqa: E402
from praatao.ui.overlay import cursor_pos, mouse_button_down  # noqa: E402

DEFAULT_OUT = Path(__file__).resolve().parent / "perf_baseline.json"

#: How many times every micro benchmark is repeated.
DEFAULT_RUNS = 25
#: How many times the end-to-end latency is measured.
DEFAULT_E2E_ROUNDS = 12
#: How long the CPU phases last.
CPU_PHASE_SECONDS = 20.0


# --------------------------------------------------------------------------
# small statistics helpers
# --------------------------------------------------------------------------
def percentile(values: Sequence[float], q: float) -> float:
    """The *q* quantile of *values* (nearest-rank, no interpolation)."""

    if not values:
        return float("nan")
    ordered = sorted(values)
    index = int(round(q * (len(ordered) - 1)))
    return ordered[max(0, min(index, len(ordered) - 1))]


def summarise(values: Sequence[float], unit: str = "ms") -> dict[str, Any]:
    """Median / p95 / min / max of a list of samples."""

    if not values:
        return {"n": 0, "unit": unit}
    return {
        "n": len(values),
        "unit": unit,
        "median": round(statistics.median(values), 3),
        "p95": round(percentile(values, 0.95), 3),
        "min": round(min(values), 3),
        "max": round(max(values), 3),
        "mean": round(statistics.fmean(values), 3),
    }


def bench(
    label: str,
    func: Callable[[], Any],
    runs: int = DEFAULT_RUNS,
    warmup: int = 3,
) -> tuple[str, dict[str, Any]]:
    """Run *func* *runs* times and report the median and the 95th percentile."""

    for _ in range(warmup):
        try:
            func()
        except Exception:  # noqa: BLE001 - a broken sensor must not stop the run
            break
    samples: list[float] = []
    for _ in range(runs):
        start = time.perf_counter()
        try:
            func()
        except Exception:  # noqa: BLE001
            pass
        samples.append((time.perf_counter() - start) * 1000.0)
    return label, summarise(samples)


def set_cursor(x: int, y: int) -> None:
    ctypes.windll.user32.SetCursorPos(int(x), int(y))


def _default_dwell() -> int:
    """The dwell time the shipped coach uses."""

    try:
        import run as praatao_run

        return int(praatao_run.DWELL_MS)
    except Exception:  # pragma: no cover
        return 0


def activate_praat() -> bool:
    """Bring the Praat window to the front.

    The coach only explains Praat while Praat is the application in
    front (a UIA hit test would otherwise pull Praat over whatever the
    user is doing).  The measurement therefore has to start with Praat
    in front, or the coach stays quiet and there is nothing to measure.
    """

    ui = PraatUI()
    objects = ui.objects_window()
    if objects is None:
        return False
    try:
        ui._activate(objects)
    except Exception:  # pragma: no cover - defensive
        return False
    time.sleep(0.4)
    return praat_has_focus()


# --------------------------------------------------------------------------
# 1. sensing cost
# --------------------------------------------------------------------------
def bench_sensors(runs: int) -> dict[str, Any]:
    """The cost of one call of every function the coach leans on."""

    ui = PraatUI()
    objects = ui.objects_window()
    if objects is None:
        print("!! Praat is not running - the sensing numbers would be empty")
        return {}

    kb = load_default()
    probe = PraatStateProbe()

    named = [e for e in ui.find_all(window=objects) if e.name and e.rect]
    by_name: dict[str, Any] = {}
    for element in named:
        by_name.setdefault(element.name.strip(), element)

    def centre(element: Any) -> tuple[int, int]:
        rect = element.rect
        return (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2

    button = by_name.get("Inspect") or (named[0] if named else None)
    if button is None:
        return {}
    bx, by = centre(button)

    # A label that the knowledge base knows, and one that it does not.
    hit_label = "View & Edit" if "View & Edit" in by_name else "Info"
    miss_label = "Zz something that does not exist"

    results: dict[str, Any] = {}
    rows: list[tuple[str, dict[str, Any]]] = []

    rows.append(bench("uia.element_at_point (button)", lambda: ui.element_at_point(bx, by), runs))
    rows.append(bench(
        "uia.element_at_point (no focus guard)",
        lambda: ui.element_at_point(bx, by, praat_only=False),
        runs,
    ))
    rows.append(bench("uia.find_all (full tree walk)", lambda: ui.find_all(), runs))
    rows.append(bench("uia.tree (Objects window)", lambda: ui.tree(objects), runs))
    rows.append(bench("uia.open_popup_items (no menu open)", lambda: ui.open_popup_items(), runs))
    rows.append(bench(
        "uia.open_popup_items (opening a menu first, cold read included)",
        lambda: _popup_items_cached(ui, objects),
        5,
    ))
    rows.append(bench("kb.lookup (exact hit)", lambda: kb.lookup(hit_label, "ButtonControl"), runs))
    rows.append(bench("kb.lookup (miss -> full scan)", lambda: kb.lookup(miss_label), runs))
    rows.append(bench("kb.normalize_key", lambda: normalize_key("View & Edit"), runs))
    rows.append(bench("kb.search", lambda: kb.search("view edit"), runs))
    rows.append(bench("probe.fast() (UIA, no script)", lambda: probe.fast(), runs))
    rows.append(bench("probe.quick() (window titles)", lambda: probe.quick(), runs))
    rows.append(bench("cursor_pos()", cursor_pos, runs))
    rows.append(bench("mouse_button_down()", lambda: mouse_button_down(1), runs))
    rows.append(bench("praat_has_focus()", praat_has_focus, runs))
    rows.append(bench("_menu_popup_open()", _menu_popup_open, runs))

    # The canvas grab needs a drawing area.
    try:
        from praatao.sensors.canvas import CanvasSensor

        canvas = CanvasSensor(ui)
        regions = canvas.regions(refresh=True)
        if regions:
            region = regions[0]
            rows.append(bench(
                "canvas.capture (screen grab)",
                lambda: canvas.capture(region),
                max(5, runs // 5),
            ))
            rows.append(bench(
                "canvas.regions (cached list)",
                lambda: canvas.regions(),
                runs,
            ))
    except Exception as exc:  # noqa: BLE001
        print(f"!! canvas sensor unavailable: {exc}")

    for label, stats in rows:
        results[label] = stats
    if _POPUP_READ_MS:
        results["uia.open_popup_items (menu open, cached)"] = summarise(
            _POPUP_READ_MS
        )
    return results


# --------------------------------------------------------------------------
# 2 + 3. pipeline cost and end-to-end latency
# --------------------------------------------------------------------------
class InstrumentedCoach:
    """The real coach, with the interesting calls timed.

    The coach is driven exactly like the shipped program: the same timers
    (``_tick`` every 45 ms, ``_mouse_poll`` every 10 ms), the same hover
    logic.  Only the calls we want to see are wrapped.
    """

    def __init__(self) -> None:
        import run as praatao_run

        self.praatao_run = praatao_run
        self.app = praatao_run.Praatao(lang="zh", use_llm=False, ui_backend="qt")
        app = self.app

        self.samples: dict[str, list[float]] = {
            "hit_test": [],
            "kb_lookup": [],
            "advice": [],
            "card_render": [],
            "spotlight": [],
            "tick_duration": [],
            "tick_period": [],
            "mouse_poll_gap": [],
            "final_tick": [],
        }
        self.tick_starts: list[float] = []
        self.card_events: list[dict[str, Any]] = []
        self._last_tick_start = 0.0
        self._tick_open = 0.0
        self._last_poll_start = 0.0

        # The wrappers have to be in place *before* the timers are
        # started: the coach re-schedules itself with ``self._mouse_poll``,
        # so a wrapper installed afterwards would get a second timer, and
        # the two timers would keep resetting each other.
        self._wrap()

        app.host.after(praatao_run.MOUSE_POLL_MS, app._mouse_poll)
        app.host.after(praatao_run.POLL_MS, app._tick)

    # -- instrumentation ------------------------------------------------
    def _wrap(self) -> None:
        app = self.app
        samples = self.samples

        def timed(name: str, func: Callable[..., Any]) -> Callable[..., Any]:
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                start = time.perf_counter()
                try:
                    return func(*args, **kwargs)
                finally:
                    samples[name].append((time.perf_counter() - start) * 1000.0)

            return wrapper

        app._element_under_cursor = timed("hit_test", app._element_under_cursor)
        app.advisor._lookup = timed("kb_lookup", app.advisor._lookup)
        app.advisor.advise = timed("advice", app.advisor.advise)
        app.card.show = timed("card_render", app.card.show)
        app.spot.show = timed("spotlight", app.spot.show)

        original_tick = app._tick

        def tick() -> None:
            now = time.perf_counter()
            if self._last_tick_start:
                samples["tick_period"].append((now - self._last_tick_start) * 1000.0)
            self._last_tick_start = now
            self.tick_starts.append(now)
            self._tick_open = now
            start = time.perf_counter()
            try:
                original_tick()
            finally:
                duration = (time.perf_counter() - start) * 1000.0
                samples["tick_duration"].append(duration)

        app._tick = tick

        # The mouse poll runs every 10 ms.  The gap between two of its
        # runs is the longest the interface thread was busy, which is
        # what the pointer "feels".
        original_poll = app._mouse_poll

        def poll() -> None:
            now = time.perf_counter()
            if self._last_poll_start:
                samples["mouse_poll_gap"].append((now - self._last_poll_start) * 1000.0)
            self._last_poll_start = now
            original_poll()

        app._mouse_poll = poll

        original_show = app.card.show

        def show(*args: Any, **kwargs: Any) -> Any:
            event = {"t": time.perf_counter(), "signature": kwargs.get("signature")}
            self.card_events.append(event)
            result = original_show(*args, **kwargs)
            event["t_done"] = time.perf_counter()
            # The tick that drew the card is the one that matters for the
            # latency: everything before it was waiting.
            event["tick_duration"] = (event["t_done"] - self._tick_open) * 1000.0
            return result

        app.card.show = show

    # -- driving --------------------------------------------------------
    def pump(self, seconds: float) -> None:
        """Run the Qt event loop for *seconds*."""

        deadline = time.perf_counter() + seconds
        while time.perf_counter() < deadline:
            self.app.pump()
            time.sleep(0.002)

    def wait_for_card(self, timeout: float = 2.0) -> dict[str, Any] | None:
        """Wait until the card is shown again."""

        start = len(self.card_events)
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            self.app.pump()
            time.sleep(0.002)
            if len(self.card_events) > start:
                return self.card_events[-1]
        return None

    def close(self) -> None:
        try:
            self.app.quit()
        except Exception:  # noqa: BLE001
            pass


def _popup_items_cached(ui: PraatUI, objects: Any) -> int:
    """Read the items of an open menu, twice (cold and warm).

    Only the warm read is timed: the cold one has to open the menu
    first, and that is the job of another benchmark.
    """

    ui.open_menu(objects, "Open", keep_open=True)
    try:
        ui.open_popup_items()  # cold: the popup has to be read
        start = time.perf_counter()
        items = ui.open_popup_items()
        _POPUP_READ_MS.append((time.perf_counter() - start) * 1000.0)
        return len(items)
    finally:
        ui.close_popup(objects)


#: The times of the warm popup reads.
_POPUP_READ_MS: list[float] = []


def bench_pipeline(runs: int) -> dict[str, Any]:
    """The tutor's own work: KB lookup, advice building, card drawing."""

    ui = PraatUI()
    objects = ui.objects_window()
    if objects is None:
        return {}
    kb = load_default()
    from praatao.tutor.advisor import Advisor

    advisor = Advisor(kb, lang="zh", llm=None)
    element = ui.find("View & Edit") or ui.find("Info")
    if element is None:
        return {}

    rows = [
        bench("advisor.advise (KB hit)", lambda: advisor.advise(element), runs),
        bench(
            "advisor.advise (unknown control)",
            lambda: advisor.advise(_FakeElement("Totally Unknown Widget")),
            runs,
        ),
    ]
    return {label: stats for label, stats in rows}


class _FakeElement:
    """An element the knowledge base knows nothing about."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.control_type = "ButtonControl"
        self.automation_id = ""
        self.hwnd = 0
        self.rect = (0, 0, 10, 10)
        self.window_title = "Praat Objects"
        self.depth = 2
        self.enabled = True


def bench_end_to_end(rounds: int) -> dict[str, Any]:
    """From "the pointer rests on a control" to "the card is on screen"."""

    ui = PraatUI()
    objects = ui.objects_window()
    if objects is None:
        print("!! Praat is not running - no end-to-end numbers")
        return {}

    named = [e for e in ui.find_all(window=objects) if e.name and e.rect]
    # Buttons that have a stable place on the Objects window.
    wanted = ("Inspect", "Info", "Remove", "Copy...", "Rename...", "Sound help")
    targets = []
    for element in named:
        if element.name.strip() in wanted:
            targets.append(element)
    if len(targets) < 3:
        targets = [e for e in named if e.name.strip() and "rowColumn" not in e.name]
    if not targets:
        return {}

    # A spot on the desktop, between the Praat windows: the pointer can
    # wait there without resting on a control, and the card (which is
    # drawn next to a Praat control) never covers it.
    park = (1000, 400)

    coach = InstrumentedCoach()
    latencies: list[float] = []
    stage_latencies: list[dict[str, float]] = []
    final_ticks: list[float] = []
    hit_counts: list[int] = []
    disturbed: list[int] = []
    try:
        # Praat has to be the application in front, otherwise the coach
        # stays quiet (and there is nothing to measure).
        activate_praat()
        # Move the pointer away from any control and let the card settle.
        set_cursor(*park)
        coach.pump(0.6)

        for index in range(rounds):
            target = targets[index % len(targets)]
            rect = target.rect
            x = (rect[0] + rect[2]) // 2
            y = (rect[1] + rect[3]) // 2

            set_cursor(*park)
            coach.pump(0.35)

            before = {name: len(v) for name, v in coach.samples.items()}
            start = time.perf_counter()
            set_cursor(x, y)
            event = coach.wait_for_card(timeout=2.0)
            if event is None:
                continue
            latency = (event["t_done"] - start) * 1000.0
            # Somebody else (another program, another agent) moved the
            # pointer: the round says nothing about the coach then.
            if cursor_pos() != (x, y):
                disturbed.append(index + 1)
                continue
            latencies.append(latency)
            final_ticks.append(event.get("tick_duration", 0.0))
            print(f"    round {index + 1}: {latency:7.1f} ms  "
                  f"({target.name.strip()})")

            # How often the coach hit-tested while the pointer waited.
            hits = len(coach.samples["hit_test"]) - before.get("hit_test", 0)
            hit_counts.append(hits)

            stage = {"total": latency}
            for name in ("kb_lookup", "advice", "card_render", "spotlight"):
                delta = coach.samples[name][before.get(name, 0):]
                if delta:
                    stage[name] = sum(delta)
            stage_latencies.append(stage)
            time.sleep(0.05)
    finally:
        coach.close()

    result: dict[str, Any] = {
        "end_to_end": summarise(latencies),
        "disturbed_rounds": disturbed,
        "stages": {
            # Once per hover.
            "kb_lookup": summarise([s.get("kb_lookup", 0.0) for s in stage_latencies]),
            "advice_building": summarise(
                [s.get("advice", 0.0) for s in stage_latencies]
            ),
            "card_render": summarise(
                [s.get("card_render", 0.0) for s in stage_latencies]
            ),
            "spotlight": summarise([s.get("spotlight", 0.0) for s in stage_latencies]),
            # The tick that finally drew the card.
            "final_tick": summarise(final_ticks),
            # Repeated work while the pointer waited.
            "hit_test_per_call": summarise(coach.samples["hit_test"]),
            "hit_tests_per_hover": summarise(hit_counts, unit="x"),
            "tick_duration": summarise(coach.samples["tick_duration"]),
            "tick_period": summarise(coach.samples["tick_period"]),
            "gui_thread_block_ms": summarise(coach.samples["mouse_poll_gap"]),
        },
    }
    # Everything that is not work: the dwell and the wait for the next tick.
    if latencies and stage_latencies:
        work = [
            s.get("kb_lookup", 0.0) + s.get("advice", 0.0)
            + s.get("card_render", 0.0) + s.get("spotlight", 0.0)
            for s in stage_latencies
        ]
        result["stages"]["work_once_per_hover"] = summarise(work)
        result["stages"]["waiting_dwell_and_poll"] = summarise(
            [lat - w for lat, w in zip(latencies, work)]
        )
    if disturbed:
        print(f"!! {len(disturbed)} round(s) were disturbed by another "
              f"program moving the pointer: {disturbed}")
    return result


# --------------------------------------------------------------------------
# 4. CPU load of the coach process
# --------------------------------------------------------------------------
def _legacy_coach_command() -> list[str]:
    """A command that starts the coach with the *old* implementations.

    The CPU is measured in a separate process, so the patches of
    :func:`install_legacy_behaviour` have to be applied there too.  A
    tiny wrapper script does that.
    """

    wrapper = Path(os.environ.get("TEMP", ".")) / "praatao_legacy_coach.py"
    experiments = str(Path(__file__).resolve().parent)
    wrapper.write_text(
        "import sys\n"
        f"sys.path.insert(0, {experiments!r})\n"
        "from perf_probe import install_legacy_behaviour\n"
        "install_legacy_behaviour()\n"
        "import run\n"
        "raise SystemExit(run.main())\n",
        encoding="utf-8",
    )
    return [sys.executable, str(wrapper), "--no-llm", "--ui", "qt"]


def bench_cpu(seconds: float = CPU_PHASE_SECONDS, legacy: bool = False) -> dict[str, Any]:
    """CPU time and wall time of the coach while the mouse idles / moves."""

    try:
        import psutil
    except Exception:  # pragma: no cover
        print("!! psutil is missing - the CPU numbers are skipped")
        return {}

    ui = PraatUI()
    objects = ui.objects_window()
    if objects is None:
        print("!! Praat is not running - no CPU numbers")
        return {}

    log = Path(os.environ.get("TEMP", ".")) / "praatao_perf_coach.log"
    command = _legacy_coach_command() if legacy else [
        sys.executable, "run.py", "--no-llm", "--ui", "qt",
    ]
    process = subprocess.Popen(
        command,
        cwd=str(ROOT),
        stdout=log.open("wb"),
        stderr=subprocess.STDOUT,
    )
    try:
        # Give the coach time to start up and settle.
        time.sleep(4.0)
        try:
            handle = psutil.Process(process.pid)
        except Exception:  # pragma: no cover
            return {}

        # The mouse has to be over Praat, and Praat has to be in front,
        # otherwise the coach does nothing at all and the numbers are
        # meaningless.
        ui._activate(objects)
        time.sleep(0.6)

        button = ui.find("Inspect") or ui.find("Info")
        if button is None:
            named = [e for e in ui.find_all(window=objects) if e.name and e.rect]
            button = named[0]
        rect = button.rect
        bx = (rect[0] + rect[2]) // 2
        by = (rect[1] + rect[3]) // 2

        def phase(label: str, mover: Callable[[], None]) -> dict[str, Any]:
            cpu0 = handle.cpu_times()
            wall0 = time.perf_counter()
            deadline = wall0 + seconds
            while time.perf_counter() < deadline:
                mover()
                time.sleep(0.016)
            cpu1 = handle.cpu_times()
            wall = time.perf_counter() - wall0
            cpu = (cpu1.user - cpu0.user) + (cpu1.system - cpu0.system)
            return {
                "phase": label,
                "seconds": round(wall, 2),
                "cpu_seconds": round(cpu, 3),
                "cpu_percent": round(100.0 * cpu / wall, 2) if wall else 0.0,
                "user_seconds": round(cpu1.user - cpu0.user, 3),
                "system_seconds": round(cpu1.system - cpu0.system, 3),
            }

        set_cursor(bx, by)
        time.sleep(0.4)
        idle = phase("mouse idle over Praat", lambda: None)

        # A sweep over the Objects window, the way a hand moves.
        points = [(bx, by)]
        for element in ui.find_all(window=objects):
            if element.name and element.rect and element.name.strip() in (
                "Inspect", "Info", "Remove", "Copy...", "Rename..."
            ):
                r = element.rect
                points.append(((r[0] + r[2]) // 2, (r[1] + r[3]) // 2))
        if len(points) < 2:
            points = [(bx, by), (bx + 3, by + 3)]

        state = {"index": 0}

        def mover() -> None:
            state["index"] = (state["index"] + 1) % len(points)
            set_cursor(*points[state["index"]])

        moving = phase("mouse moving over Praat", mover)
        return {"idle": idle, "moving": moving}
    finally:
        try:
            process.terminate()
            process.wait(timeout=5)
        except Exception:  # noqa: BLE001
            try:
                process.kill()
            except Exception:  # noqa: BLE001
                pass
        try:
            log.unlink()
        except OSError:
            pass


# --------------------------------------------------------------------------
# 5. false triggers
# --------------------------------------------------------------------------
#: How long the pointer stays on a control during a sweep, in ms.  A short
#: stay is "the pointer merely passed over".
SWEEP_STEPS_MS = (20, 40, 60, 100, 150, 200, 240, 280, 320)


def bench_false_triggers(
    sweeps: int = 6,
    steps_ms: Sequence[int] = SWEEP_STEPS_MS,
) -> dict[str, Any]:
    """How often does the card appear for a control the pointer passed over?

    The pointer visits a row of buttons and stays on each of them for
    ``step_ms`` - the "sweep across the window" case.  A card that appears
    there is a false trigger.
    """

    ui = PraatUI()
    objects = ui.objects_window()
    if objects is None:
        return {}
    named = [
        e for e in ui.find_all(window=objects)
        if e.name and e.rect and e.name.strip() in (
            "Rename...", "Copy...", "Inspect", "Info", "Remove", "Sound help",
            "View & Edit", "Play",
        )
    ]
    if not named:
        return {}

    coach = InstrumentedCoach()
    try:
        activate_praat()
        points = coach_points(named)
        # A spot on the desktop where no control waits: the pointer can
        # wait there, the card is not there, and the coach sends the card
        # away.  Every visit starts from there, so the card of the
        # previous visit cannot cover the control of the next one.
        park = (1000, 400)
        set_cursor(*park)
        coach.pump(0.4)

        rows: list[dict[str, Any]] = []
        for step in steps_ms:
            shown_before = len(coach.card_events)
            visited = 0
            disturbed = 0
            for _ in range(sweeps):
                for point in points:
                    set_cursor(*park)
                    coach.pump(0.08)
                    set_cursor(*point)
                    coach.pump(step / 1000.0)
                    if cursor_pos() != point:
                        # Somebody else moved the pointer: this visit
                        # says nothing about the coach.
                        disturbed += 1
                        continue
                    visited += 1
            shown = len(coach.card_events) - shown_before
            rows.append({
                "dwell_per_control_ms": step,
                "controls_visited": visited,
                "cards_shown": shown,
                "false_trigger_rate": round(shown / visited, 4) if visited else 0.0,
                "disturbed_visits": disturbed,
            })
            # Let the cards go before the next sweep.
            set_cursor(*park)
            coach.pump(2.5)
        return {"sweeps": rows}
    finally:
        coach.close()


def coach_points(named: Iterable[Any]) -> list[tuple[int, int]]:
    points: list[tuple[int, int]] = []
    for element in named:
        rect = element.rect
        points.append(((rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2))
    return points


def bench_deep_probe(runs: int = 8) -> dict[str, Any]:
    """The cost of the deep probe (the one that sends a Praat script).

    This is measured **last**: the script makes Praat busy, and a busy
    Praat blocks every read of its window, which would spoil the other
    measurements.
    """

    probe = PraatStateProbe()
    label, stats = bench(
        "probe.snapshot() (deep probe, sends a Praat script)",
        lambda: probe.snapshot(timeout=8.0),
        runs,
    )
    time.sleep(1.0)
    return {label: stats}


# --------------------------------------------------------------------------
# measuring the old, slow behaviour with the same harness
# --------------------------------------------------------------------------
def install_legacy_behaviour() -> list[str]:
    """Put the implementations of *before* the performance work back.

    The point is comparability: the numbers of "before" and "after" then
    come from the same harness, on the same machine, at the same moment.
    Only the parts that were changed are restored; everything else (the
    knowledge base content, the Praat state, the card) is untouched.
    """

    import run as praatao_run
    from praatao.sensors import canvas as canvas_module
    from praatao.sensors import praat_state as state_module
    from praatao.sensors import uia as uia_module
    from praatao.tutor import kb as kb_module

    restored: list[str] = []

    # 0. The dwell was 320 ms.
    praatao_run.DWELL_MS = 320
    restored.append("dwell 320 ms")

    # 1. Every tick asked the accessibility tree again.
    def legacy_element_under_cursor(self, x, y):
        if self.ui is None:
            return None
        try:
            return self.ui.element_at_point(x, y)
        except Exception:
            return None

    praatao_run.Praatao._element_under_cursor = legacy_element_under_cursor
    restored.append("hit-test cache")

    # 2. The mouse poll only watched the button, so the dwell started at
    #    the tick that noticed the pointer.
    def legacy_mouse_poll(self) -> None:
        if not self._running:
            return
        x, y = cursor_pos()
        down = mouse_button_down(1)
        if down and not self._last_mouse_down:
            self._handle_click(x, y)
        self._last_mouse_down = down
        self.host.after(praatao_run.MOUSE_POLL_MS, self._mouse_poll)

    praatao_run.Praatao._mouse_poll = legacy_mouse_poll
    restored.append("dwell measured from the pointer's arrival")

    # 3. The knowledge base was scanned entry by entry.
    def legacy_lookup(self, element_name, control_type=None):
        key = normalize_key(element_name)
        if not key:
            return None
        exact = self._by_alias.get(key)
        if exact:
            return self._choose(exact, control_type)
        best_len = 0
        best = []
        for alias_key, bucket in self._by_alias.items():
            if len(alias_key) < 3:
                continue
            if alias_key in key and len(alias_key) > best_len:
                best_len = len(alias_key)
                best = list(bucket)
        if best:
            return self._choose(best, control_type)
        best_score = 0
        best_kw = []
        for entry in self._entries:
            for kw in entry.keywords:
                kw_norm = normalize_key(kw)
                if len(kw_norm) >= 2 and kw_norm in key and len(kw_norm) > best_score:
                    best_score = len(kw_norm)
                    best_kw = [entry]
                elif len(kw_norm) >= 2 and kw_norm in key and len(kw_norm) == best_score:
                    if entry not in best_kw:
                        best_kw.append(entry)
        if best_kw:
            return self._choose(best_kw, control_type)
        return None

    kb_module.KnowledgeBase.lookup = legacy_lookup
    restored.append("knowledge base index")

    # 4. The Objects list box was searched for on every poll.
    def legacy_listing():
        try:
            import uiautomation as auto
        except Exception:
            return None
        try:
            window = auto.WindowControl(
                searchDepth=1, ClassName=state_module.PRAAT_SHELL_CLASS,
                Name="Praat Objects",
            )
            if not window.Exists(0.2):
                return None
            listing = window.ListControl(searchDepth=4, ClassName="ListBox")
            if not listing.Exists(0.2):
                return None
        except Exception:
            return None
        return listing

    state_module._objects_listing = legacy_listing
    restored.append("objects-list cache")

    # 5. The drawing areas were found by walking the accessibility tree.
    def legacy_regions(self, refresh: bool = False):
        from praatao.sensors.canvas import CanvasRegion, _object_name
        from praatao.sensors.uia import _safe_rect, _text

        now = time.monotonic()
        if not refresh and self._regions and (now - self._cached_at) < self.CACHE_TTL:
            return self._regions
        found: list[Any] = []
        for window in self.ui.windows() + self.ui.editor_windows():
            control = self.ui._control_from_window(window)
            if control is None:
                continue
            for node, _depth in self.ui._iter_controls(control, max_depth=6):
                class_name = _text(node, "ClassName").strip().casefold()
                if class_name not in canvas_module.CANVAS_CLASSES:
                    continue
                rect = _safe_rect(node)
                if rect is None or rect[2] - rect[0] < 40 or rect[3] - rect[1] < 40:
                    continue
                found.append(
                    CanvasRegion(
                        hwnd=window.hwnd,
                        canvas_hwnd=window.hwnd,
                        window_title=window.title,
                        window_kind=window.kind,
                        rect=rect,
                        object_name=_object_name(window.title),
                    )
                )
        self._regions = found
        self._cached_at = now
        return found

    canvas_module.CanvasSensor.regions = legacy_regions
    restored.append("drawing-area lookup")

    # 6. The menu was looked for by walking every top-level window.
    def legacy_menu_popup_open() -> bool:
        import win32gui

        found = False

        def _find(hwnd: int, _extra: object) -> None:
            nonlocal found
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return
                if (win32gui.GetClassName(hwnd) or "") != "#32768":
                    return
                owner = win32gui.GetWindow(hwnd, 4)
                if not owner:
                    return
                owner_class = (win32gui.GetClassName(owner) or "")
            except Exception:
                return
            if "praat" in owner_class.casefold():
                found = True

        try:
            win32gui.EnumWindows(_find, None)
        except Exception:
            return False
        return found

    uia_module._menu_popup_open = legacy_menu_popup_open
    restored.append("menu check")

    # 7. The items of an open menu were found by walking the tree.
    def legacy_open_popup_items(self, window=None):
        windows = [window] if window is not None else self._refresh_windows()
        for win in windows:
            if win is None:
                continue
            control = self._control_from_window(win)
            if control is None:
                continue
            for node, _depth in self._iter_controls(control, max_depth=self.MAX_DEPTH):
                if uia_module._text(node, "ControlTypeName") != "MenuControl":
                    continue
                items: list[Any] = []
                for child in self._children(node):
                    if uia_module._text(child, "ControlTypeName") == "SeparatorControl":
                        continue
                    items.append(self._element_from(child, depth=2, window_title=win.title))
                if items:
                    return items
        return []

    uia_module.PraatUI.open_popup_items = legacy_open_popup_items
    restored.append("menu item lookup")

    return restored


# --------------------------------------------------------------------------
# the report
# --------------------------------------------------------------------------
def print_table(sections: dict[str, dict[str, Any]]) -> None:
    width = 78
    for title, rows in sections.items():
        if not rows:
            continue
        print()
        print("=" * width)
        print(f" {title}")
        print("=" * width)
        print(f" {'what':<44s} {'n':>4s} {'median':>10s} {'p95':>10s} {'min':>9s} {'max':>9s}")
        print("-" * width)
        for label, stats in rows.items():
            if not isinstance(stats, dict) or "median" not in stats:
                print(f" {label:<44s} {stats}")
                continue
            unit = stats.get("unit", "ms")
            print(
                f" {label:<44s} {stats['n']:>4d} "
                f"{stats['median']:>8.3f}{unit:>2s} "
                f"{stats['p95']:>8.3f}{unit:>2s} "
                f"{stats['min']:>7.3f}{unit:>2s} "
                f"{stats['max']:>7.3f}{unit:>2s}"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(DEFAULT_OUT),
                        help="where to write the JSON result")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS,
                        help="repetitions per micro benchmark")
    parser.add_argument("--rounds", type=int, default=DEFAULT_E2E_ROUNDS,
                        help="repetitions of the end-to-end measurement")
    parser.add_argument("--cpu-seconds", type=float, default=CPU_PHASE_SECONDS,
                        help="length of each CPU phase")
    parser.add_argument("--quick", action="store_true",
                        help="a fast, less precise run")
    parser.add_argument("--skip-cpu", action="store_true",
                        help="do not start a second coach process")
    parser.add_argument("--dwell", type=int, default=None,
                        help="override the dwell time (ms) of the coach, so "
                             "the false-trigger rate can be measured for a "
                             "different setting")
    parser.add_argument("--legacy", action="store_true",
                        help="measure the behaviour of *before* the "
                             "performance work (the same harness, the old "
                             "implementations)")
    parser.add_argument("--only", default="",
                        help="comma separated list of the parts to measure: "
                             "sensors, pipeline, end_to_end, false_triggers, "
                             "cpu, deep_probe (default: everything)")
    args = parser.parse_args(argv)

    if args.quick:
        args.runs = max(5, args.runs // 5)
        args.rounds = max(3, args.rounds // 3)
        args.cpu_seconds = min(args.cpu_seconds, 5.0)

    original_cursor = cursor_pos()
    print(f"mouse starts at {original_cursor}")

    dwell_ms = args.dwell
    legacy: list[str] = []
    if args.legacy:
        legacy = install_legacy_behaviour()
        print("legacy mode: " + ", ".join(legacy))
    if dwell_ms is not None:
        import run as praatao_run

        praatao_run.DWELL_MS = int(dwell_ms)
        print(f"dwell overridden: {dwell_ms} ms")

    report: dict[str, Any] = {
        "meta": {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "machine": platform.platform(),
            "python": platform.python_version(),
            "runs": args.runs,
            "rounds": args.rounds,
            "dwell_ms": dwell_ms if dwell_ms is not None else _default_dwell(),
            "legacy": legacy,
        }
    }

    only = {part.strip() for part in args.only.split(",") if part.strip()}

    def wanted(part: str) -> bool:
        return not only or part in only

    try:
        if wanted("sensors"):
            print("\n[1/6] sensing cost ...")
            report["sensors"] = bench_sensors(args.runs)
        else:
            report["sensors"] = {}

        if wanted("pipeline"):
            print("[2/6] tutor pipeline ...")
            report["pipeline"] = bench_pipeline(args.runs)
        else:
            report["pipeline"] = {}

        if wanted("end_to_end"):
            print("[3/6] end-to-end latency ...")
            report["end_to_end"] = bench_end_to_end(args.rounds)
        else:
            report["end_to_end"] = {}

        if wanted("false_triggers"):
            print("[4/6] false triggers ...")
            report["false_triggers"] = bench_false_triggers()
        else:
            report["false_triggers"] = {}

        if not args.skip_cpu and wanted("cpu"):
            print(f"[5/6] CPU load ({args.cpu_seconds:g} s per phase) ...")
            report["cpu"] = bench_cpu(args.cpu_seconds, legacy=bool(legacy))
        else:
            report["cpu"] = {}

        if wanted("deep_probe"):
            print("[6/6] the deep probe (last: it makes Praat busy) ...")
            report["deep_probe"] = bench_deep_probe()
        else:
            report["deep_probe"] = {}
    finally:
        set_cursor(*original_cursor)
        print(f"\nmouse restored to {original_cursor}")

    sections = {
        "Sensing cost (one call)": report.get("sensors", {}),
        "Tutor pipeline": report.get("pipeline", {}),
        "Deep probe (last)": report.get("deep_probe", {}),
        "End-to-end latency (pointer rests -> card on screen)":
            report.get("end_to_end", {}).get("end_to_end", {}),
        "End-to-end, broken down":
            report.get("end_to_end", {}).get("stages", {}),
    }
    print_table(sections)

    cpu = report.get("cpu", {})
    if cpu:
        print()
        print("=" * 78)
        print(" CPU load of the coach process")
        print("=" * 78)
        for key in ("idle", "moving"):
            phase = cpu.get(key)
            if not phase:
                continue
            print(
                f" {phase['phase']:<32s} {phase['seconds']:>6.1f} s wall, "
                f"{phase['cpu_seconds']:>6.2f} s CPU "
                f"({phase['cpu_percent']:>5.1f} % of one core)"
            )

    false = report.get("false_triggers", {})
    if false:
        print()
        print("=" * 78)
        print(" False triggers (the pointer merely passing over a control)")
        print("=" * 78)
        print(f" dwell setting: {report['meta'].get('dwell_ms', '?')} ms")
        print(f" {'stay on a control':>18s} {'controls':>9s} {'cards':>6s} {'rate':>7s}")
        for row in false.get("sweeps", []):
            print(
                f" {row['dwell_per_control_ms']:>15d} ms "
                f"{row['controls_visited']:>9d} {row['cards_shown']:>6d} "
                f"{100 * row['false_trigger_rate']:>6.1f} %"
            )

    out = Path(args.out)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
