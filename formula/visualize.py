"""Race Telemetry Report - Formula 67 project proposal.

Opens a native window (just like the game window) displaying a full
telemetry dashboard built from the CSV stats produced by
``StatsLogger.export_to_csv()``.  A PNG snapshot of the same dashboard
is also written to ``reports/telemetry_report.png`` for archival.

Strictly follows the academic proposal (4.3 Data Analysis Report):

  *  3 statistical tables (one per feature):
       Table 1 - Speed Statistics       (Mean / Max / Min / Std Dev)
       Table 2 - Steering Input Summary (Direction / Count / Percentage)
       Table 3 - Lap Time Statistics    (Mean / Min / Max / Median / Std Dev)

  *  4 distinct graphs (no repeated type, two categories of data):
       Graph 1 - Speed vs Time              (Line, time-series)
       Graph 2 - Speed Distribution         (Histogram)
       Graph 3 - Nitro Duration vs Speed    (Scatter, multi-race)
       Graph 4 - Steering Direction         (Pie chart)

Units: speed in pixels per second (px/s), time in seconds.

Run from CLI:
    python visualize.py                 # opens dashboard as a new window
    python visualize.py --race-id 5
    python visualize.py --no-show       # only save PNG, no window

Auto-called from main.py at the end of every race (silent PNG save).
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")  # render off-screen; the UI is pygame, not Tk.
import matplotlib.pyplot as plt
from matplotlib import patches
from matplotlib.patches import FancyBboxPatch, Rectangle


# ---------------------------------------------------------------------------
# Constants & theme
# ---------------------------------------------------------------------------
PX_PER_FRAME_TO_PX_PER_SEC = 60.0

COLORS = {
    "bg":         "#07070a",
    "panel":      "#11111a",
    "panel_2":    "#15151f",
    "line":       "#1d1d28",
    "line_2":     "#2a2a36",
    "text":       "#ffffff",
    "text_2":     "#d4d4dc",
    "muted":      "#898997",
    "dim":        "#585866",
    "red":        "#e10600",
    "red_soft":   "#ff2d2d",
    "gold":       "#ffc300",
    "green":      "#00d56a",
    "silver":     "#c4c4cc",
    "bronze":     "#cd7f32",
    "cyan":       "#21e6f0",
    "purple":     "#b14fff",
    "pink":       "#ff5fa8",
    "orange":     "#ff8a00",
}
DRIVER_COLORS = {
    "Player":      "#ffffff",
    "Verstappen":  "#1e41ff",
    "Hamilton":    "#27f4d2",
    "Leclerc":     "#dc0000",
    "Norris":      "#ff8000",
    "Russell":     "#27f4d2",
}


# ---------------------------------------------------------------------------
# CSV loading + statistics (pandas-based, per proposal requirement)
# ---------------------------------------------------------------------------
def _read_csv_df(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()

def _filter_race(df: pd.DataFrame, race_id: int) -> pd.DataFrame:
    if df.empty or "race_id" not in df.columns:
        return df.iloc[0:0]
    return df[df["race_id"].astype("Int64") == race_id]

def _safe_float(val, default=0.0) -> float:
    try:
        if val is None or pd.isna(val):
            return default
        return float(val)
    except (TypeError, ValueError):
        return default

def _safe_int(val, default=0) -> int:
    try:
        if val is None or pd.isna(val):
            return default
        return int(float(val))
    except (TypeError, ValueError):
        return default

def _speed_stats(speed_df: pd.DataFrame) -> Dict:
    if speed_df.empty or "speed_px_s" not in speed_df.columns:
        return dict(mean=0, max=0, min=0, std=0, samples=0)
    s = pd.to_numeric(speed_df["speed_px_s"], errors="coerce").dropna() \
        * PX_PER_FRAME_TO_PX_PER_SEC
    if s.empty:
        return dict(mean=0, max=0, min=0, std=0, samples=0)
    desc = s.agg(["mean", "max", "min"])
    return dict(
        mean=float(desc["mean"]),
        max=float(desc["max"]),
        min=float(desc["min"]),
        std=float(s.std(ddof=0)) if len(s) > 1 else 0.0,
        samples=int(len(s)),
    )

def _lap_stats(lap_df: pd.DataFrame) -> Dict:
    if lap_df.empty or "lap_time_s" not in lap_df.columns:
        return dict(mean=0, min=0, max=0, median=0, std=0, count=0)
    t = pd.to_numeric(lap_df["lap_time_s"], errors="coerce").dropna()
    if t.empty:
        return dict(mean=0, min=0, max=0, median=0, std=0, count=0)
    return dict(
        mean=float(t.mean()),
        min=float(t.min()),
        max=float(t.max()),
        median=float(t.median()),
        std=float(t.std(ddof=0)) if len(t) > 1 else 0.0,
        count=int(len(t)),
    )

def _steering_stats(steering_df: pd.DataFrame) -> Dict:
    if steering_df.empty:
        return dict(left=0, right=0, left_pct=0.0, right_pct=0.0, total=0)
    row = steering_df.iloc[0]
    left = _safe_int(row.get("left_count"))
    right = _safe_int(row.get("right_count"))
    total = max(1, left + right)
    return dict(
        left=left, right=right,
        left_pct=left / total * 100,
        right_pct=right / total * 100,
        total=left + right,
    )

def _build_speed_series(speed_df: pd.DataFrame):
    if speed_df.empty or "timestamp" not in speed_df.columns:
        return np.array([]), np.array([])
    df = speed_df.copy()
    df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
    df["speed_px_s"] = pd.to_numeric(df["speed_px_s"], errors="coerce")
    df = df.dropna(subset=["timestamp", "speed_px_s"])
    if df.empty:
        return np.array([]), np.array([])
    t0 = float(df["timestamp"].iloc[0])
    t = (df["timestamp"].to_numpy() - t0)
    s = df["speed_px_s"].to_numpy() * PX_PER_FRAME_TO_PX_PER_SEC
    return t, s

def _build_speed_histogram(speed_df: pd.DataFrame, bins: int = 18):
    if speed_df.empty or "speed_px_s" not in speed_df.columns:
        return np.array([]), 0.0
    s = pd.to_numeric(speed_df["speed_px_s"], errors="coerce").dropna() \
        * PX_PER_FRAME_TO_PX_PER_SEC
    if s.empty:
        return np.array([]), 0.0
    return s.to_numpy(), float(s.max() - s.min())

def _build_nitro_scatter(nitro_events: pd.DataFrame,
                         nitro_aggregates: pd.DataFrame):
    use_events = not nitro_events.empty
    df = nitro_events if use_events else nitro_aggregates
    if df.empty:
        return pd.DataFrame(columns=["x", "y", "race"])
    df = df.copy()
    if use_events:
        df["x"] = pd.to_numeric(df.get("duration_s"), errors="coerce")
    else:
        df["x"] = pd.to_numeric(df.get("nitro_duration_s"), errors="coerce")
    df["y"] = (pd.to_numeric(df.get("avg_speed_px_s"), errors="coerce")
               * PX_PER_FRAME_TO_PX_PER_SEC)
    df["race"] = pd.to_numeric(df.get("race_id"), errors="coerce")
    df = df.dropna(subset=["x", "y", "race"])
    df["race"] = df["race"].astype(int)
    return df[["x", "y", "race"]]

def _build_race_payload(
    race_id: int,
    race_summary_row: pd.Series,
    laps_r: pd.DataFrame,
    speeds_r: pd.DataFrame,
    competitors_r: pd.DataFrame,
    steering_r: pd.DataFrame,
    nitro_events_all: pd.DataFrame,
    nitro_aggregates: pd.DataFrame,
) -> Dict:
    speed_stats = _speed_stats(speeds_r)
    lap_stats = _lap_stats(laps_r)
    steering_stats = _steering_stats(steering_r)
    speed_t, speed_s = _build_speed_series(speeds_r)
    speed_samples, _ = _build_speed_histogram(speeds_r)
    nitro_scatter = _build_nitro_scatter(nitro_events_all, nitro_aggregates)

    lap_count = 0
    if not competitors_r.empty and "lap_reached" in competitors_r.columns:
        lap_count = int(pd.to_numeric(competitors_r["lap_reached"],
                                      errors="coerce").fillna(0).max() or 0)
    if not lap_count and not laps_r.empty and "lap_number" in laps_r.columns:
        lap_count = int(pd.to_numeric(laps_r["lap_number"],
                                      errors="coerce").fillna(0).max() or 0)

    winner = None
    if not competitors_r.empty:
        finished = competitors_r.copy()
        finished["rank_n"] = pd.to_numeric(finished.get("rank"),
                                           errors="coerce")
        finished["finish_n"] = pd.to_numeric(finished.get("finish_time_s"),
                                             errors="coerce")
        finished = finished.dropna(subset=["rank_n", "finish_n"])
        if not finished.empty:
            winner = str(finished.sort_values("rank_n").iloc[0]["name"])

    competitors_sorted = competitors_r.copy()
    if not competitors_sorted.empty and "rank" in competitors_sorted.columns:
        competitors_sorted["rank_sort"] = pd.to_numeric(
            competitors_sorted["rank"], errors="coerce").fillna(99)
        competitors_sorted = competitors_sorted.sort_values("rank_sort")
    competitors_payload = []
    for c in competitors_sorted.to_dict(orient="records"):
        ft = c.get("finish_time_s")
        bl = c.get("best_lap_s")
        competitors_payload.append({
            "name": c.get("name"),
            "rank": _safe_int(c.get("rank")),
            "finish_time": (_safe_float(ft)
                            if ft not in (None, "") and not pd.isna(ft)
                            else None),
            "best_lap": (_safe_float(bl)
                         if bl not in (None, "") and not pd.isna(bl)
                         else None),
            "lap_reached": _safe_int(c.get("lap_reached")),
        })

    fastest = None
    for c in competitors_payload:
        if c["best_lap"] is None:
            continue
        if fastest is None or c["best_lap"] < fastest["best_lap"]:
            fastest = c

    return {
        "race_id": race_id,
        "lap_count": lap_count,
        "winner": winner,
        "fastest": fastest,
        "summary": {
            "total_time": _safe_float(race_summary_row.get("total_time_s")),
            "best_lap": _safe_float(race_summary_row.get("best_lap_s")),
            "max_speed_px_s": (
                _safe_float(race_summary_row.get("max_speed_px_per_frame"))
                * PX_PER_FRAME_TO_PX_PER_SEC),
            "collisions": _safe_int(race_summary_row.get("collisions")),
            "nitro_duration": _safe_float(
                race_summary_row.get("nitro_duration_s")),
        },
        "speed_stats": speed_stats,
        "lap_stats": lap_stats,
        "steering": steering_stats,
        "speed_t": speed_t,
        "speed_s": speed_s,
        "speed_samples": speed_samples,
        "nitro_scatter": nitro_scatter,
        "competitors": competitors_payload,
    }


# ---------------------------------------------------------------------------
# Layout (all heights in INCHES; total figure height = sum + gaps)
# ---------------------------------------------------------------------------
SECTION_HEIGHTS = {
    "top_margin":   0.30,
    "header":       1.00,
    "info_bar":     1.10,
    "coverage":     1.35,
    "kpi_row":      1.60,
    "sec1_head":    0.55,
    "stats_tbl":    2.30,
    "sec2_head":    0.55,
    "charts_r1":    2.80,
    "charts_r2":    2.80,
    "sec3_head":    0.55,
    "standings":    2.70,
    "footer":       0.45,
    "bottom_margin": 0.30,
}
SECTION_ORDER = [
    "top_margin", "header", "info_bar", "coverage", "kpi_row",
    "sec1_head", "stats_tbl",
    "sec2_head", "charts_r1", "charts_r2",
    "sec3_head", "standings",
    "footer", "bottom_margin",
]
GAP_INCHES = 0.18
FIG_WIDTH = 16.0

def _compute_layout():
    """Return a dict of (y_bottom, height) in figure fraction for each key."""
    total = sum(SECTION_HEIGHTS.values()) + GAP_INCHES * (len(SECTION_ORDER) - 1)
    rects = {}
    cursor = total
    for i, key in enumerate(SECTION_ORDER):
        h = SECTION_HEIGHTS[key]
        top = cursor
        bottom = top - h
        rects[key] = (bottom / total, h / total)
        cursor = bottom
        if i < len(SECTION_ORDER) - 1:
            cursor -= GAP_INCHES
    return rects, total


# ---------------------------------------------------------------------------
# Matplotlib drawing primitives + panels
# ---------------------------------------------------------------------------
def _driver_color(name: Optional[str]) -> str:
    return DRIVER_COLORS.get(name or "", COLORS["silver"])

def _hide_axes(ax):
    ax.set_xticks([]); ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_facecolor("none")

def _panel_axes(fig, rect, facecolor=None, accent=None):
    """Create a styled panel axes at ``rect = (x, y, w, h)`` (figure frac)."""
    ax = fig.add_axes(rect)
    _hide_axes(ax); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.add_patch(Rectangle(
        (0, 0), 1, 1, transform=ax.transAxes,
        facecolor=facecolor or COLORS["panel"],
        edgecolor=COLORS["line"], lw=1))
    if accent:
        ax.add_patch(Rectangle(
            (0, 0), 0.005, 1, transform=ax.transAxes,
            facecolor=accent, edgecolor="none"))
    return ax

def _section_header(fig, rect, number: str, title: str, subtitle: str = ""):
    ax = fig.add_axes(rect)
    _hide_axes(ax); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.add_patch(Rectangle((0.0, 0.18), 0.038, 0.64,
                           transform=ax.transAxes,
                           facecolor=COLORS["red"], edgecolor="none"))
    ax.text(0.019, 0.50, number, transform=ax.transAxes,
            ha="center", va="center",
            color="#fff", fontsize=13, fontweight="bold", style="italic")
    ax.text(0.048, 0.60, title.upper(), transform=ax.transAxes,
            ha="left", va="center",
            color=COLORS["text"], fontsize=13, fontweight="bold")
    if subtitle:
        ax.text(0.048, 0.28, subtitle.upper(), transform=ax.transAxes,
                ha="left", va="center",
                color=COLORS["muted"], fontsize=8.5, fontweight="bold",
                family="monospace")
    ax.plot([0.30, 1.0], [0.50, 0.50],
            color=COLORS["line"], lw=0.8, transform=ax.transAxes)
    ax.plot([0.30, 0.36], [0.50, 0.50],
            color=COLORS["red"], lw=1.6, transform=ax.transAxes)

def _draw_header(fig, rect, payload):
    x, y, w, h = rect
    ax = _panel_axes(fig, rect, facecolor=COLORS["panel"])

    ax.add_patch(Rectangle((0, 0.95), 1, 0.05, transform=ax.transAxes,
                           facecolor=COLORS["red"], edgecolor="none"))

    ax.add_patch(Rectangle((0.015, 0.20), 0.028, 0.55,
                           transform=ax.transAxes,
                           facecolor=COLORS["red"], edgecolor="none"))
    ax.text(0.029, 0.475, "F", transform=ax.transAxes,
            ha="center", va="center", color="#fff",
            fontsize=22, fontweight="bold", style="italic")
    ax.add_patch(Rectangle((0.045, 0.20), 0.028, 0.55,
                           transform=ax.transAxes,
                           facecolor="#fff", edgecolor="none"))
    ax.text(0.059, 0.475, "67", transform=ax.transAxes,
            ha="center", va="center", color="#000",
            fontsize=17, fontweight="bold", style="italic")

    ax.text(0.090, 0.60, "FORMULA 67", transform=ax.transAxes,
            ha="left", va="center",
            color=COLORS["text"], fontsize=19, fontweight="bold")
    ax.add_patch(Rectangle((0.090, 0.33), 0.013, 0.010,
                           transform=ax.transAxes,
                           facecolor=COLORS["red"], edgecolor="none"))
    ax.text(0.108, 0.33, "RACE CONTROL  ·  LIVE TIMING & TELEMETRY",
            transform=ax.transAxes, ha="left", va="center",
            color=COLORS["muted"], fontsize=8.5, fontweight="bold")

    ax.add_patch(Rectangle((0.740, 0.42), 0.068, 0.22,
                           transform=ax.transAxes,
                           facecolor=COLORS["red"], edgecolor="none"))
    ax.text(0.774, 0.53, "LIVE", transform=ax.transAxes,
            ha="center", va="center",
            color="#fff", fontsize=10, fontweight="bold", style="italic")
    ax.text(0.820, 0.60, "GENERATED", transform=ax.transAxes,
            ha="left", va="center",
            color=COLORS["muted"], fontsize=8, fontweight="bold")
    ax.text(0.820, 0.40, payload["generated_at"],
            transform=ax.transAxes, ha="left", va="center",
            family="monospace",
            color=COLORS["text_2"], fontsize=9.5)

def _draw_info_bar(fig, rect, race):
    ax = _panel_axes(fig, rect, facecolor=COLORS["panel_2"],
                     accent=COLORS["red"])

    strip_colors = [COLORS["red"], COLORS["orange"], COLORS["gold"],
                    COLORS["green"], COLORS["cyan"], COLORS["purple"],
                    COLORS["pink"]]
    seg = 1.0 / len(strip_colors)
    for i, c in enumerate(strip_colors):
        ax.add_patch(Rectangle((i * seg, 0), seg, 0.035,
                               transform=ax.transAxes,
                               facecolor=c, edgecolor="none"))

    winner = next((c for c in race["competitors"] if c.get("rank") == 1),
                  None)
    fastest = race["fastest"]

    cells = [
        ("ROUND",            f"{race['race_id']:02d}",
         "CURRENT SESSION",   COLORS["red"],   20),
        ("WINNER",
         (winner["name"].upper() if winner and winner.get("name") else "--"),
         (f"{winner['finish_time']:.2f}S  RACE TIME"
          if winner and winner.get("finish_time") else "--"),
         COLORS["gold"], 16),
        ("FASTEST LAP",
         (fastest["name"].upper() if fastest and fastest.get("name") else "--"),
         (f"{fastest['best_lap']:.3f}S  LAP TIME"
          if fastest and fastest.get("best_lap") is not None else "--"),
         COLORS["purple"], 16),
        ("LAPS",     str(race["lap_count"] or "--"),
         "COMPLETED", COLORS["text"], 18),
        ("GRID",     str(len(race["competitors"]) or "--"),
         "DRIVERS",   COLORS["text"], 18),
        ("SESSIONS", str(race.get("total_races", "--")),
         "IN DATASET", COLORS["text"], 18),
    ]
    widths = [0.13, 0.22, 0.22, 0.14, 0.14, 0.15]
    x_cursor = 0.01
    for (label, value, sub, color, vfs), w in zip(cells, widths):

        ax.plot([x_cursor + w - 0.002, x_cursor + w - 0.002],
                [0.10, 0.92], transform=ax.transAxes,
                color=COLORS["line"], lw=0.8)
        ax.text(x_cursor + 0.015, 0.80, label, transform=ax.transAxes,
                ha="left", va="center", color=COLORS["muted"],
                fontsize=8.5, fontweight="bold")
        ax.text(x_cursor + 0.015, 0.50, value, transform=ax.transAxes,
                ha="left", va="center", color=color,
                fontsize=vfs, fontweight="bold", style="italic")
        ax.text(x_cursor + 0.015, 0.21, sub, transform=ax.transAxes,
                ha="left", va="center", color=COLORS["dim"],
                fontsize=7.5, family="monospace", fontweight="bold")
        x_cursor += w

def _draw_coverage(fig, rect, coverage):
    ax = _panel_axes(fig, rect, facecolor=COLORS["panel"],
                     accent=COLORS["red"])

    ax.text(0.015, 0.78, "◆  DATA COVERAGE", transform=ax.transAxes,
            ha="left", va="center", color=COLORS["text"],
            fontsize=12, fontweight="bold")
    ax.text(0.015, 0.52, "requirement ≥ 100 records per feature",
            transform=ax.transAxes, ha="left", va="center",
            color=COLORS["muted"], fontsize=8.5, family="monospace")
    ax.text(0.015, 0.28, f"total datasets · {len(coverage)} channels",
            transform=ax.transAxes, ha="left", va="center",
            color=COLORS["dim"], fontsize=8, family="monospace",
            fontweight="bold")

    x0 = 0.19
    gap = 0.012
    w = (1.0 - x0 - 0.015 - gap * (len(coverage) - 1)) / len(coverage)
    for i, item in enumerate(coverage):
        x = x0 + i * (w + gap)
        count = item["count"]
        color = item["color"]
        ok = count >= 100
        half = count >= 50
        badge_color = (COLORS["green"] if ok
                       else (COLORS["gold"] if half else COLORS["red"]))
        badge_text = "PASS" if ok else f"{count}/100"
        ax.add_patch(FancyBboxPatch(
            (x, 0.12), w, 0.76, transform=ax.transAxes,
            boxstyle="round,pad=0,rounding_size=0.006",
            facecolor="#0e0e16", edgecolor=COLORS["line"], lw=1))
        ax.add_patch(Rectangle((x, 0.12), 0.006, 0.76,
                               transform=ax.transAxes,
                               facecolor=color, edgecolor="none"))
        ax.text(x + 0.018, 0.74, item["label"].upper(),
                transform=ax.transAxes, ha="left", va="center",
                color=COLORS["muted"], fontsize=8, fontweight="bold")
        ax.text(x + 0.018, 0.47, f"{count:,}", transform=ax.transAxes,
                ha="left", va="center", color=color,
                fontsize=22, fontweight="bold", style="italic")
        ax.add_patch(FancyBboxPatch(
            (x + 0.018, 0.18), 0.085, 0.14, transform=ax.transAxes,
            boxstyle="round,pad=0,rounding_size=0.004",
            facecolor=badge_color, edgecolor="none"))
        ax.text(x + 0.060, 0.25, badge_text, transform=ax.transAxes,
                ha="center", va="center", color="#001",
                fontsize=8, fontweight="bold", style="italic")

def _draw_kpi_row(fig, rect, race):
    x, y, w_total, h_total = rect
    s = race["summary"]
    lap_avg = race["lap_stats"]["mean"]
    delta = (s["best_lap"] - lap_avg) if lap_avg > 0 else 0
    kpis = [
        ("RACE TIME",   f"{s['total_time']:.2f}", "s",
         f"{race['lap_count']} LAPS COMPLETED", COLORS["red"]),
        ("FASTEST LAP", f"{s['best_lap']:.2f}", "s",
         (f"{delta:+.2f}s vs AVG" if lap_avg > 0 else "PERSONAL BEST"),
         COLORS["purple"]),
        ("AVG SPEED",   f"{race['speed_stats']['mean']:.1f}", "px/s",
         f"{race['speed_stats']['samples']:,} SAMPLES",
         COLORS["cyan"]),
        ("TOP SPEED",   f"{s['max_speed_px_s']:.1f}", "px/s",
         "PEAK VELOCITY", COLORS["gold"]),
        ("INCIDENTS",   f"{s['collisions']}", "",
         "CLEAN RACE" if s["collisions"] == 0 else "CONTACTS LOGGED",
         COLORS["text"]),
        ("DRS / BOOST", f"{s['nitro_duration']:.1f}", "s",
         "TOTAL BOOST TIME", COLORS["green"]),
    ]
    gap_fig = 0.008
    w_fig = (w_total - gap_fig * (len(kpis) - 1)) / len(kpis)
    for i, (label, val, unit, sub, c) in enumerate(kpis):
        rx = x + i * (w_fig + gap_fig)
        ax = fig.add_axes([rx, y, w_fig, h_total])
        _hide_axes(ax); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
        ax.add_patch(FancyBboxPatch(
            (0.004, 0.04), 0.992, 0.92, transform=ax.transAxes,
            boxstyle="round,pad=0,rounding_size=0.02",
            facecolor=COLORS["panel_2"], edgecolor=COLORS["line"], lw=1))
        ax.add_patch(Rectangle((0.004, 0.04), 0.020, 0.92,
                               transform=ax.transAxes,
                               facecolor=c, edgecolor="none"))
        ax.add_patch(Rectangle((0.024, 0.04), 0.972, 0.030,
                               transform=ax.transAxes,
                               facecolor=c, edgecolor="none", alpha=0.30))

        ax.add_patch(patches.Circle(
            (0.075, 0.80), 0.020, transform=ax.transAxes,
            facecolor=c, edgecolor="none"))
        ax.text(0.11, 0.80, label, transform=ax.transAxes,
                ha="left", va="center", color=COLORS["muted"],
                fontsize=9, fontweight="bold")

        ax.text(0.06, 0.48, val, transform=ax.transAxes,
                ha="left", va="center", color=COLORS["text"],
                fontsize=26, fontweight="bold", style="italic")
        if unit:
            ax.text(0.94, 0.48, unit, transform=ax.transAxes,
                    ha="right", va="center", color=COLORS["muted"],
                    fontsize=10, family="monospace", fontweight="bold")

        ax.text(0.06, 0.16, sub, transform=ax.transAxes,
                ha="left", va="center", color=COLORS["dim"],
                fontsize=8, family="monospace", fontweight="bold")

def _draw_stats_tables(fig, rect, race):
    x, y, w_total, h_total = rect
    gap_fig = 0.012
    w_fig = (w_total - gap_fig * 2) / 3
    cards = [
        ("SPEED TRAP", COLORS["red"], "Speed Statistics",
         "units in pixels per second",
         [("Mean Speed", f"{race['speed_stats']['mean']:.2f}  px/s"),
          ("Maximum Speed", f"{race['speed_stats']['max']:.2f}  px/s"),
          ("Minimum Speed", f"{race['speed_stats']['min']:.2f}  px/s"),
          ("Standard Deviation",
           f"{race['speed_stats']['std']:.2f}  px/s")]),
        ("DRIVER INPUT", COLORS["cyan"], "Steering Input",
         "direction · count · percentage",
         [("Left",
           f"{race['steering']['left']:,}   "
           f"({race['steering']['left_pct']:.1f}%)"),
          ("Right",
           f"{race['steering']['right']:,}   "
           f"({race['steering']['right_pct']:.1f}%)"),
          ("Total", f"{race['steering']['total']:,}   inputs")]),
        ("LAP TIME", COLORS["gold"], "Lap Time Statistics",
         "units in seconds",
         [("Mean Lap Time", f"{race['lap_stats']['mean']:.2f}  s"),
          ("Minimum Time", f"{race['lap_stats']['min']:.2f}  s"),
          ("Maximum Time", f"{race['lap_stats']['max']:.2f}  s"),
          ("Median", f"{race['lap_stats']['median']:.2f}  s"),
          ("Standard Deviation",
           f"{race['lap_stats']['std']:.2f}  s")]),
    ]
    for i, (tag, color, title, sub, rows) in enumerate(cards):
        rx = x + i * (w_fig + gap_fig)
        ax = fig.add_axes([rx, y, w_fig, h_total])
        _hide_axes(ax); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
        ax.add_patch(Rectangle((0, 0), 1, 1, transform=ax.transAxes,
                               facecolor=COLORS["panel"],
                               edgecolor=COLORS["line"], lw=1))
        ax.add_patch(Rectangle((0, 0), 0.008, 1,
                               transform=ax.transAxes,
                               facecolor=color, edgecolor="none"))

        ax.add_patch(Rectangle((0.035, 0.88), 0.24, 0.075,
                               transform=ax.transAxes,
                               facecolor=color, edgecolor="none"))
        ax.text(0.155, 0.918, tag, transform=ax.transAxes,
                ha="center", va="center", color="#001",
                fontsize=8, fontweight="bold", style="italic")

        ax.text(0.035, 0.80, title.upper(), transform=ax.transAxes,
                ha="left", va="center", color=COLORS["text"],
                fontsize=11.5, fontweight="bold")
        ax.text(0.035, 0.735, sub.upper(), transform=ax.transAxes,
                ha="left", va="center", color=COLORS["muted"],
                fontsize=8, family="monospace", fontweight="bold")
        ax.plot([0.035, 0.965], [0.69, 0.69], color=COLORS["red"], lw=1.2,
                transform=ax.transAxes)

        y_top = 0.61
        y_bot = 0.08
        dy = (y_top - y_bot) / max(len(rows), 1)
        for j, (k, v) in enumerate(rows):
            yi = y_top - dy * (j + 0.5)
            ax.text(0.045, yi, k, transform=ax.transAxes, ha="left",
                    va="center", color=COLORS["text_2"], fontsize=10)
            ax.text(0.955, yi, v, transform=ax.transAxes, ha="right",
                    va="center", color=COLORS["text"], fontsize=10,
                    family="monospace", fontweight="bold")
            if j < len(rows) - 1:
                ax.plot([0.045, 0.955],
                        [yi - dy * 0.5, yi - dy * 0.5],
                        color=COLORS["line"], lw=0.5,
                        transform=ax.transAxes)

def _style_chart_ax(ax, xlabel, ylabel):
    ax.set_facecolor(COLORS["panel_2"])
    for spine in ax.spines.values():
        spine.set_edgecolor(COLORS["line"])
        spine.set_linewidth(1.0)
    ax.tick_params(colors=COLORS["muted"], which="both",
                   labelsize=8.5, length=0, pad=4)
    ax.grid(True, color=COLORS["line"], lw=0.5, alpha=0.6)
    ax.set_axisbelow(True)
    ax.set_xlabel(xlabel.upper(), color=COLORS["muted"], fontsize=8.5,
                  fontweight="bold", labelpad=6)
    ax.set_ylabel(ylabel.upper(), color=COLORS["muted"], fontsize=8.5,
                  fontweight="bold", labelpad=6)

def _draw_chart_card(fig, rect, tag, color, title, sub):
    """Draw a chart card frame and return the inner (chart axes, inner rect)."""
    x, y, w, h = rect
    ax = _panel_axes(fig, rect, facecolor=COLORS["panel"], accent=color)
    ax.add_patch(Rectangle((0.020, 0.900), 0.13, 0.060,
                           transform=ax.transAxes,
                           facecolor=color, edgecolor="none"))
    ax.text(0.085, 0.930, tag, transform=ax.transAxes,
            ha="center", va="center", color="#001",
            fontsize=8, fontweight="bold", style="italic")
    ax.text(0.020, 0.840, title.upper(), transform=ax.transAxes,
            ha="left", va="center", color=COLORS["text"],
            fontsize=11, fontweight="bold")
    ax.text(0.020, 0.790, sub.upper(), transform=ax.transAxes,
            ha="left", va="center", color=COLORS["muted"],
            fontsize=8, family="monospace", fontweight="bold")

    inner_x = x + w * 0.07
    inner_y = y + h * 0.15
    inner_w = w * 0.88
    inner_h = h * 0.55
    chart_ax = fig.add_axes([inner_x, inner_y, inner_w, inner_h])
    return chart_ax

def _draw_charts_row(fig, row_rect, race, row_index: int):
    """Draw a row of 2 chart cards.  row_index: 0 = top row, 1 = bottom row."""
    x, y, w, h = row_rect
    gap_fig = 0.012
    col_w = (w - gap_fig) / 2
    left_rect = (x, y, col_w, h)
    right_rect = (x + col_w + gap_fig, y, col_w, h)

    if row_index == 0:

        c1 = _draw_chart_card(fig, left_rect,
                              "TIME SERIES", COLORS["red"],
                              "Speed Trace",
                              "velocity over the entire race")
        _style_chart_ax(c1, "time (s)", "speed (px/s)")
        t, s = race["speed_t"], race["speed_s"]
        if len(t) > 0:
            c1.fill_between(t, s, s.min() if len(s) else 0,
                            color=COLORS["red"], alpha=0.22, linewidth=0)
            c1.plot(t, s, color=COLORS["red"], lw=1.4)
            c1.set_xlim(float(t.min()), float(t.max()))

        c2 = _draw_chart_card(fig, right_rect,
                              "DISTRIBUTION", COLORS["purple"],
                              "Speed Distribution",
                              "frequency across speed bins")
        _style_chart_ax(c2, "speed range (px/s)", "frequency")
        samples = race["speed_samples"]
        if len(samples) > 0:
            c2.hist(samples, bins=18, color=COLORS["purple"],
                    edgecolor=COLORS["panel_2"], linewidth=0.8)
    else:

        c3 = _draw_chart_card(fig, left_rect,
                              "DRS BOOST", COLORS["green"],
                              "Boost Duration vs Avg Speed",
                              "one point per DRS burst across all races")
        _style_chart_ax(c3, "nitro duration (s)", "avg speed (px/s)")
        scat = race["nitro_scatter"]
        cur = race["race_id"]
        if not scat.empty:
            others = scat[scat["race"] != cur]
            mine = scat[scat["race"] == cur]
            if not others.empty:
                c3.scatter(others["x"], others["y"], s=22,
                           color=COLORS["green"], alpha=0.70,
                           edgecolors="none",
                           label=f"other races ({len(others)})")
            if not mine.empty:
                c3.scatter(mine["x"], mine["y"], s=60,
                           color=COLORS["red"],
                           edgecolors="#fff", linewidths=1.2,
                           label=f"this race ({len(mine)})", zorder=5)
            c3.legend(loc="upper right", fontsize=8, frameon=False,
                      labelcolor=COLORS["text_2"])

        x4, y4, w4, h4 = right_rect
        _panel_axes(fig, right_rect, facecolor=COLORS["panel"],
                    accent=COLORS["gold"])

        frame = fig.axes[-1]
        frame.add_patch(Rectangle((0.020, 0.900), 0.13, 0.060,
                                  transform=frame.transAxes,
                                  facecolor=COLORS["gold"], edgecolor="none"))
        frame.text(0.085, 0.930, "DIRECTION",
                   transform=frame.transAxes, ha="center", va="center",
                   color="#001", fontsize=8, fontweight="bold", style="italic")
        frame.text(0.020, 0.840, "STEERING BIAS",
                   transform=frame.transAxes, ha="left", va="center",
                   color=COLORS["text"], fontsize=11, fontweight="bold")
        frame.text(0.020, 0.790, "LEFT vs RIGHT INPUT PROPORTION",
                   transform=frame.transAxes, ha="left", va="center",
                   color=COLORS["muted"], fontsize=8,
                   family="monospace", fontweight="bold")

        inner_x = x4 + w4 * 0.08
        inner_y = y4 + h4 * 0.08
        inner_w = w4 * 0.84
        inner_h = h4 * 0.60
        c4 = fig.add_axes([inner_x, inner_y, inner_w, inner_h])
        _hide_axes(c4)
        c4.set_facecolor(COLORS["panel"])
        left = race["steering"]["left"]
        right = race["steering"]["right"]
        if left + right > 0:
            sizes = [left, right]
            labels = [
                f"LEFT  {left:,}\n{race['steering']['left_pct']:.1f}%",
                f"RIGHT  {right:,}\n{race['steering']['right_pct']:.1f}%",
            ]
            cols = [COLORS["red"], COLORS["cyan"]]
            c4.pie(
                sizes, labels=labels, colors=cols,
                startangle=90, counterclock=False,
                wedgeprops=dict(width=0.38, edgecolor=COLORS["bg"],
                                linewidth=3),
                textprops=dict(color=COLORS["text_2"], fontsize=9.5,
                               fontweight="bold"))
            c4.text(0, 0.06, f"{left + right:,}",
                    ha="center", va="center",
                    color=COLORS["text"], fontsize=16, fontweight="bold",
                    style="italic")
            c4.text(0, -0.22, "INPUTS", ha="center", va="center",
                    color=COLORS["muted"], fontsize=8, fontweight="bold",
                    family="monospace")

def _draw_standings(fig, rect, race):
    ax = _panel_axes(fig, rect, facecolor=COLORS["panel"])
    competitors = race["competitors"]
    if not competitors:
        ax.text(0.5, 0.5, "no classification data",
                transform=ax.transAxes, ha="center", va="center",
                color=COLORS["muted"], fontsize=10)
        return

    col_xs = [0.025, 0.060, 0.105, 0.44, 0.60, 0.76, 0.92]
    headers = ["POS", "", "DRIVER", "BEST LAP", "RACE TIME", "GAP", "LAPS"]
    aligns = ["left", "left", "left", "right", "right", "right", "right"]
    for hx, h, a in zip(col_xs, headers, aligns):
        ax.text(hx, 0.90, h, transform=ax.transAxes,
                ha=a, va="center", color=COLORS["muted"],
                fontsize=8.5, fontweight="bold")
    ax.plot([0.02, 0.98], [0.85, 0.85], color=COLORS["red"], lw=1.2,
            transform=ax.transAxes)

    winner_time = next((c["finish_time"] for c in competitors
                        if c.get("rank") == 1
                        and c.get("finish_time") is not None), None)

    n = len(competitors)
    top = 0.82
    bot = 0.04
    row_h = (top - bot) / max(n, 1)

    for i, c in enumerate(competitors):
        rank = c.get("rank") or 0
        name = c.get("name") or "Unknown"
        ft = c.get("finish_time")
        bl = c.get("best_lap")
        laps = c.get("lap_reached") or 0
        y_c = top - row_h * (i + 0.5)

        if i % 2 == 1:
            ax.add_patch(Rectangle((0.02, y_c - row_h * 0.46),
                                   0.96, row_h * 0.92,
                                   transform=ax.transAxes,
                                   facecolor=COLORS["panel_2"],
                                   edgecolor="none", alpha=0.5))

        if rank == 1:
            ax.add_patch(Rectangle((0.02, y_c - row_h * 0.46),
                                   0.96, row_h * 0.92,
                                   transform=ax.transAxes,
                                   facecolor=COLORS["gold"],
                                   edgecolor="none", alpha=0.10))

        pill_color = {1: COLORS["gold"], 2: COLORS["silver"],
                      3: COLORS["bronze"]}.get(rank, "#1a1a25")
        pill_text_color = (COLORS["muted"] if rank > 3 else "#001a08")
        ax.add_patch(FancyBboxPatch(
            (col_xs[0] - 0.003, y_c - row_h * 0.30), 0.030, row_h * 0.60,
            transform=ax.transAxes,
            boxstyle="round,pad=0,rounding_size=0.004",
            facecolor=pill_color,
            edgecolor=(COLORS["line_2"] if rank > 3 else "none"),
            lw=1 if rank > 3 else 0))
        ax.text(col_xs[0] + 0.012, y_c, str(rank),
                transform=ax.transAxes, ha="center", va="center",
                color=pill_text_color, fontsize=11, fontweight="bold",
                style="italic")

        dc = _driver_color(name)
        ax.add_patch(patches.Circle(
            (col_xs[1] + 0.010, y_c), 0.008,
            transform=ax.transAxes,
            facecolor=dc, edgecolor="#000", lw=0.8))

        name_color = COLORS["gold"] if rank == 1 else COLORS["text"]
        ax.text(col_xs[2], y_c, name.upper(),
                transform=ax.transAxes, ha="left", va="center",
                color=name_color, fontsize=10.5, fontweight="bold")

        bl_txt = f"{bl:.2f}s" if bl is not None else "--"
        ft_txt = f"{ft:.2f}s" if ft is not None else "DNF"
        ax.text(col_xs[3], y_c, bl_txt, transform=ax.transAxes,
                ha="right", va="center", color=COLORS["text"],
                fontsize=10, family="monospace", fontweight="bold")
        ax.text(col_xs[4], y_c, ft_txt, transform=ax.transAxes,
                ha="right", va="center", color=COLORS["text"],
                fontsize=10, family="monospace", fontweight="bold")

        if rank == 1:
            ax.add_patch(Rectangle(
                (col_xs[5] - 0.060, y_c - row_h * 0.22),
                0.060, row_h * 0.44,
                transform=ax.transAxes,
                facecolor=COLORS["red"], edgecolor="none"))
            ax.text(col_xs[5] - 0.030, y_c, "LEADER",
                    transform=ax.transAxes, ha="center", va="center",
                    color="#fff", fontsize=8, fontweight="bold",
                    style="italic")
        elif ft is not None and winner_time is not None:
            gap = ft - winner_time
            ax.text(col_xs[5], y_c, f"+{gap:.3f}",
                    transform=ax.transAxes, ha="right", va="center",
                    color=COLORS["text_2"], fontsize=10,
                    family="monospace")
        else:
            ax.text(col_xs[5], y_c, "--",
                    transform=ax.transAxes, ha="right", va="center",
                    color=COLORS["dim"], fontsize=10,
                    family="monospace")

        ax.text(col_xs[6], y_c, str(laps),
                transform=ax.transAxes, ha="right", va="center",
                color=COLORS["text"], fontsize=10,
                family="monospace", fontweight="bold")

def _draw_footer(fig, rect):
    x, y, w, h = rect
    ax = fig.add_axes(rect)
    _hide_axes(ax); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_facecolor(COLORS["bg"])
    ax.plot([0, 1], [0.95, 0.95], color=COLORS["line"], lw=1,
            transform=ax.transAxes)
    ax.text(0.02, 0.45, "F1 / 67   TELEMETRY REPORT",
            transform=ax.transAxes, ha="left", va="center",
            color=COLORS["red"], fontsize=9, fontweight="bold",
            style="italic")
    ax.text(0.50, 0.45,
            "generated from stats/*.csv via pandas",
            transform=ax.transAxes, ha="center", va="center",
            color=COLORS["dim"], fontsize=8, family="monospace",
            fontweight="bold")
    ax.text(0.98, 0.45,
            "VELOCITY · PX/S   |   TIMING · SECONDS",
            transform=ax.transAxes, ha="right", va="center",
            color=COLORS["dim"], fontsize=8, family="monospace",
            fontweight="bold")


# ---------------------------------------------------------------------------
# Figure composition
# ---------------------------------------------------------------------------
def _render_dashboard(payload, race, coverage):
    """Build the full matplotlib figure and return (fig, total_height)."""
    rects, total_in = _compute_layout()

    plt.rcParams.update({
        "font.family": ["DejaVu Sans"],
        "axes.edgecolor": COLORS["line"],
        "axes.labelcolor": COLORS["muted"],
        "xtick.color": COLORS["muted"],
        "ytick.color": COLORS["muted"],
    })

    fig = plt.figure(figsize=(FIG_WIDTH, total_in), dpi=100)
    fig.patch.set_facecolor(COLORS["bg"])

    margin_x = 0.015

    def R(key):
        y_b, h = rects[key]
        return (margin_x, y_b, 1 - 2 * margin_x, h)

    _draw_header(fig, R("header"), payload)
    _draw_info_bar(fig, R("info_bar"), race)
    _draw_coverage(fig, R("coverage"), coverage)
    _draw_kpi_row(fig, R("kpi_row"), race)
    _section_header(fig, R("sec1_head"), "01",
                    "Timing Data", "// statistical summary")
    _draw_stats_tables(fig, R("stats_tbl"), race)
    _section_header(fig, R("sec2_head"), "02",
                    "Telemetry", "// channel data")
    _draw_charts_row(fig, R("charts_r1"), race, 0)
    _draw_charts_row(fig, R("charts_r2"), race, 1)
    _section_header(fig, R("sec3_head"), "03",
                    "Race Classification", "// final result")
    _draw_standings(fig, R("standings"), race)
    _draw_footer(fig, R("footer"))
    return fig, total_in


# ---------------------------------------------------------------------------
# Pygame viewer - used instead of Tk/MacOSX because Tcl/Tk 8.6 shipped with
# the stock Python.org / pyenv build crashes on macOS 14+ with:
#   "-[NSApplication macOSVersion]: unrecognized selector"
# pygame is already a project dependency, so re-using it keeps things simple.
# ---------------------------------------------------------------------------
def _show_in_pygame_window(
        png_path: str,
        title: str = "Formula 67 · Telemetry Dashboard",
        race_ids: Optional[List[int]] = None,
        current_race: Optional[int] = None,
        render_fn: Optional[Callable[[int], Optional[str]]] = None):
    """Resizable, scrollable dashboard viewer with round switching.

    Parameters
    ----------
    race_ids : list[int]
        All available race ids for the ◀/▶ selector.
    current_race : int
        The race id currently rendered.
    render_fn : callable(int) -> str
        Re-renders a PNG for the given race id and returns the path.
    """
    try:
        import pygame
    except Exception as exc:
        print(f"[visualize] pygame not available ({exc}); skipping window")
        return

    try:
        pygame.display.quit()
    except Exception:
        pass
    pygame.display.init()
    try:
        pygame.font.init()
    except Exception:
        pass

    race_ids = list(race_ids) if race_ids else []
    race_ids.sort()
    if current_race is None and race_ids:
        current_race = race_ids[-1]

    def _load_img():
        try:
            return pygame.image.load(png_path)
        except Exception as exc:
            print(f"[visualize] could not load {png_path}: {exc}")
            return None

    img = _load_img()
    if img is None:
        pygame.display.quit()
        return
    img_w, img_h = img.get_size()

    info = pygame.display.Info()
    screen_w = info.current_w or 1600
    screen_h = info.current_h or 900
    win_w = min(img_w, max(900, screen_w - 120))
    win_h = min(img_h + 44, max(640, screen_h - 160))

    TOP_BAR = 44
    flags = pygame.RESIZABLE
    screen = pygame.display.set_mode((win_w, win_h), flags)
    pygame.display.set_caption(title)

    clock = pygame.time.Clock()
    bg = (7, 7, 10)

    def _font(size, bold=True, mono=False):
        try:
            fams = ("Menlo,Consolas,Courier New,monospace" if mono
                    else "Helvetica Neue,Arial,Helvetica,sans-serif")
            return pygame.font.SysFont(fams, size, bold=bold)
        except Exception:
            return pygame.font.Font(None, size + 2)

    scroll_x = 0
    scroll_y = 0
    dragging = False
    drag_from = (0, 0)
    drag_scroll = (0, 0)
    busy_msg = ""
    busy_since = 0

    prev_rect = pygame.Rect(0, 0, 0, 0)
    next_rect = pygame.Rect(0, 0, 0, 0)

    def _clamp_scroll():
        nonlocal scroll_x, scroll_y
        content_h = img_h
        view_h = max(1, win_h - TOP_BAR)
        max_x = max(0, img_w - win_w)
        max_y = max(0, content_h - view_h)
        scroll_x = max(0, min(max_x, scroll_x))
        scroll_y = max(0, min(max_y, scroll_y))
        return max_x, max_y

    def _switch_race(delta: int):
        """Switch to another race id by index delta (-1 or +1)."""
        nonlocal img, img_w, img_h, current_race, scroll_y, busy_msg, busy_since
        if not race_ids or render_fn is None or current_race is None:
            return
        try:
            idx = race_ids.index(current_race)
        except ValueError:
            idx = len(race_ids) - 1
        new_idx = max(0, min(len(race_ids) - 1, idx + delta))
        if race_ids[new_idx] == current_race:
            return
        new_rid = race_ids[new_idx]
        busy_msg = f"Loading round {new_rid:02d}…"
        busy_since = pygame.time.get_ticks()

        _draw_frame(loading=True)
        pygame.display.flip()

        new_path = render_fn(new_rid)
        if new_path:
            new_img = _load_img()
            if new_img is not None:
                img = new_img
                img_w, img_h = img.get_size()
                current_race = new_rid
                scroll_y = 0
        busy_msg = ""

    def _draw_top_bar():
        nonlocal prev_rect, next_rect
        bar = pygame.Surface((win_w, TOP_BAR), pygame.SRCALPHA)
        bar.fill((12, 12, 20, 245))
        pygame.draw.rect(bar, (225, 6, 0), (0, TOP_BAR - 2, win_w, 2))

        f_label = _font(9, bold=True)
        f_big = _font(18, bold=True)
        f_tip = _font(10, bold=True, mono=True)

        brand = f_big.render("FORMULA 67", True, (230, 230, 235))
        bar.blit(brand, (16, 10))
        acc = f_label.render("TELEMETRY DASHBOARD", True, (150, 150, 165))
        bar.blit(acc, (16 + brand.get_width() + 12, 18))

        if race_ids and current_race is not None:
            try:
                idx = race_ids.index(current_race)
            except ValueError:
                idx = len(race_ids) - 1
            total = len(race_ids)
            has_prev = idx > 0
            has_next = idx < total - 1

            label_txt = f_label.render("ROUND", True, (150, 150, 165))
            value_txt = f_big.render(
                f"{current_race:02d}", True, (255, 220, 80))
            meta_txt = f_tip.render(f"{idx + 1} / {total}",
                                    True, (140, 140, 155))

            arrow_size = 26
            gap = 10
            group_w = (arrow_size + gap + label_txt.get_width() + 6
                       + value_txt.get_width() + gap
                       + meta_txt.get_width() + gap + arrow_size)
            group_x = max(16, (win_w - group_w) // 2)
            cy = TOP_BAR // 2

            prev_rect = pygame.Rect(group_x, cy - arrow_size // 2,
                                    arrow_size, arrow_size)
            prev_col = (225, 6, 0) if has_prev else (60, 60, 72)
            pygame.draw.rect(bar, prev_col, prev_rect, border_radius=6)
            pts = [(prev_rect.right - 9, prev_rect.top + 6),
                   (prev_rect.left + 9, prev_rect.centery),
                   (prev_rect.right - 9, prev_rect.bottom - 6)]
            pygame.draw.polygon(bar, (255, 255, 255), pts)

            lx = prev_rect.right + gap
            bar.blit(label_txt, (lx, cy - label_txt.get_height() // 2 - 2))
            lx += label_txt.get_width() + 6
            bar.blit(value_txt, (lx, cy - value_txt.get_height() // 2))
            lx += value_txt.get_width() + gap
            bar.blit(meta_txt, (lx, cy - meta_txt.get_height() // 2))
            lx += meta_txt.get_width() + gap

            next_rect = pygame.Rect(lx, cy - arrow_size // 2,
                                    arrow_size, arrow_size)
            next_col = (225, 6, 0) if has_next else (60, 60, 72)
            pygame.draw.rect(bar, next_col, next_rect, border_radius=6)
            pts = [(next_rect.left + 9, next_rect.top + 6),
                   (next_rect.right - 9, next_rect.centery),
                   (next_rect.left + 9, next_rect.bottom - 6)]
            pygame.draw.polygon(bar, (255, 255, 255), pts)
        else:
            prev_rect = pygame.Rect(0, 0, 0, 0)
            next_rect = pygame.Rect(0, 0, 0, 0)

        hint_txt = f_tip.render(
            "← →  round    ↑ ↓ wheel  scroll    Esc  exit",
            True, (160, 160, 175))
        bar.blit(hint_txt,
                 (win_w - hint_txt.get_width() - 16,
                  TOP_BAR // 2 - hint_txt.get_height() // 2))

        screen.blit(bar, (0, 0))

    def _draw_frame(loading: bool = False):
        screen.fill(bg)

        off_x = max(0, (win_w - img_w) // 2) - scroll_x
        off_y = TOP_BAR - scroll_y
        screen.blit(img, (off_x, off_y))

        _, max_y = _clamp_scroll()
        if max_y > 0:
            view_h = win_h - TOP_BAR
            track_w = 8
            track_x = win_w - track_w - 2
            pygame.draw.rect(screen, (30, 30, 38),
                             (track_x, TOP_BAR, track_w, view_h))
            thumb_h = max(30, int(view_h * view_h / img_h))
            thumb_y = TOP_BAR + int((view_h - thumb_h) * scroll_y / max_y)
            pygame.draw.rect(screen, (225, 6, 0),
                             (track_x, thumb_y, track_w, thumb_h),
                             border_radius=3)

        _draw_top_bar()

        if loading:
            overlay = pygame.Surface((win_w, win_h), pygame.SRCALPHA)
            overlay.fill((8, 8, 12, 180))
            screen.blit(overlay, (0, 0))
            f = _font(22, bold=True)
            txt = f.render(busy_msg or "Rendering…",
                           True, (255, 220, 80))
            screen.blit(txt, ((win_w - txt.get_width()) // 2,
                              (win_h - txt.get_height()) // 2))

    running = True
    while running:
        step = 60
        page = max(1, (win_h - TOP_BAR) - 80)
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.VIDEORESIZE:
                win_w, win_h = ev.w, ev.h
                screen = pygame.display.set_mode((win_w, win_h), flags)
            elif ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif ev.key == pygame.K_LEFT:
                    _switch_race(-1)
                elif ev.key == pygame.K_RIGHT:
                    _switch_race(+1)
                elif ev.key == pygame.K_DOWN:
                    scroll_y += step
                elif ev.key == pygame.K_UP:
                    scroll_y -= step
                elif ev.key == pygame.K_PAGEDOWN or ev.key == pygame.K_SPACE:
                    scroll_y += page
                elif ev.key == pygame.K_PAGEUP:
                    scroll_y -= page
                elif ev.key == pygame.K_HOME:
                    scroll_y = 0
                elif ev.key == pygame.K_END:
                    scroll_y = img_h
            elif ev.type == pygame.MOUSEWHEEL:
                if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                    scroll_x -= ev.y * 60
                else:
                    scroll_y -= ev.y * 60
                scroll_x -= ev.x * 60
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                pos = pygame.mouse.get_pos()
                if prev_rect.collidepoint(pos):
                    _switch_race(-1)
                elif next_rect.collidepoint(pos):
                    _switch_race(+1)
                elif pos[1] > TOP_BAR:
                    dragging = True
                    drag_from = pos
                    drag_scroll = (scroll_x, scroll_y)
            elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                dragging = False
            elif ev.type == pygame.MOUSEMOTION and dragging:
                mx, my = pygame.mouse.get_pos()
                scroll_x = drag_scroll[0] + (drag_from[0] - mx)
                scroll_y = drag_scroll[1] + (drag_from[1] - my)

        _clamp_scroll()
        _draw_frame()
        pygame.display.flip()
        clock.tick(60)

    try:
        pygame.display.quit()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Public API + CLI
# ---------------------------------------------------------------------------
def generate_report(stats_dir: str = "stats",
                    out_dir: str = "reports",
                    race_id: Optional[int] = None,
                    open_browser: bool = False,
                    show_window: bool = False) -> Optional[str]:
    """Render the telemetry dashboard.

    Parameters
    ----------
    show_window : bool
        If True, opens the dashboard as a scrollable native window.
    open_browser : bool
        Legacy alias for ``show_window``.
    """
    if not os.path.isdir(stats_dir):
        print(f"[visualize] stats dir not found: {stats_dir}")
        return None

    race_summaries   = _read_csv_df(os.path.join(stats_dir, "race_summary.csv"))
    laps             = _read_csv_df(os.path.join(stats_dir, "lap_time.csv"))
    speeds           = _read_csv_df(os.path.join(stats_dir, "speed.csv"))
    competitors      = _read_csv_df(os.path.join(stats_dir, "competitor.csv"))
    nitros           = _read_csv_df(os.path.join(stats_dir, "nitro.csv"))
    steerings        = _read_csv_df(os.path.join(stats_dir, "steering.csv"))
    nitro_events     = _read_csv_df(os.path.join(stats_dir, "nitro_event.csv"))
    collision_events = _read_csv_df(
        os.path.join(stats_dir, "collision_event.csv"))
    steering_events  = _read_csv_df(
        os.path.join(stats_dir, "steering_event.csv"))

    if race_summaries.empty:
        print("[visualize] no race_summary.csv data found")
        return None

    race_summaries["race_id"] = pd.to_numeric(race_summaries["race_id"],
                                              errors="coerce").astype("Int64")
    race_summaries = race_summaries.dropna(subset=["race_id"])
    all_race_ids = sorted(int(x) for x
                          in race_summaries["race_id"].astype(int).unique())
    target_id = int(race_id) if race_id is not None else max(all_race_ids)

    summary_by_id = {int(rs["race_id"]): rs
                     for _, rs in race_summaries.iterrows()}
    rs = summary_by_id.get(target_id)
    if rs is None:
        print(f"[visualize] race_id {target_id} not found")
        return None

    race = _build_race_payload(
        race_id=target_id,
        race_summary_row=rs,
        laps_r=_filter_race(laps, target_id),
        speeds_r=_filter_race(speeds, target_id),
        competitors_r=_filter_race(competitors, target_id),
        steering_r=_filter_race(steerings, target_id),
        nitro_events_all=nitro_events,
        nitro_aggregates=nitros,
    )
    race["total_races"] = len(all_race_ids)

    coverage = [
        {"label": "Speed Samples",    "count": int(len(speeds)),
         "color": COLORS["cyan"]},
        {"label": "Steering Inputs",  "count": int(len(steering_events)),
         "color": COLORS["pink"]},
        {"label": "Lap Times",        "count": int(len(laps)),
         "color": COLORS["gold"]},
        {"label": "Collision Events", "count": int(len(collision_events)),
         "color": COLORS["red"]},
        {"label": "Nitro Bursts",     "count": int(len(nitro_events)),
         "color": COLORS["green"]},
    ]

    payload = {
        "generated_at": datetime.now().strftime("%a %d %b %Y · %H:%M"),
        "default_race": target_id,
        "coverage": coverage,
        "race": race,
    }

    want_window = show_window or open_browser
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "telemetry_report.png")

    # Closure captures all loaded DataFrames; the viewer uses it to
    # re-render a different race when the user clicks ◀ / ▶.
    def _render_to_png(rid: int) -> Optional[str]:
        """Render the dashboard for ``rid`` to ``out_path`` and return it."""
        rs_row = summary_by_id.get(int(rid))
        if rs_row is None:
            return None
        race_i = _build_race_payload(
            race_id=int(rid),
            race_summary_row=rs_row,
            laps_r=_filter_race(laps, int(rid)),
            speeds_r=_filter_race(speeds, int(rid)),
            competitors_r=_filter_race(competitors, int(rid)),
            steering_r=_filter_race(steerings, int(rid)),
            nitro_events_all=nitro_events,
            nitro_aggregates=nitros,
        )
        race_i["total_races"] = len(all_race_ids)
        payload_i = {
            "generated_at": datetime.now().strftime("%a %d %b %Y · %H:%M"),
            "default_race": int(rid),
            "coverage": coverage,
            "race": race_i,
        }
        fig_i, _ = _render_dashboard(payload_i, race_i, coverage)
        fig_i.savefig(out_path, facecolor=COLORS["bg"], dpi=120,
                      bbox_inches=None, pad_inches=0)
        plt.close(fig_i)
        return out_path

    _render_to_png(target_id)

    if want_window:
        _show_in_pygame_window(
            out_path,
            title=f"Formula 67 · Telemetry Dashboard",
            race_ids=all_race_ids,
            current_race=target_id,
            render_fn=_render_to_png,
        )

    return out_path

if __name__ == "__main__":
    import argparse

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(
        description="Render the Formula 67 telemetry dashboard in a window.")
    parser.add_argument("--race-id", type=int, default=None,
                        help="race id to render (default: latest)")
    parser.add_argument("--no-show", action="store_true",
                        help="only save the PNG, do not open a window")
    args = parser.parse_args()

    out = generate_report(
        stats_dir=os.path.join(BASE_DIR, "stats"),
        out_dir=os.path.join(BASE_DIR, "reports"),
        race_id=args.race_id,
        show_window=not args.no_show,
    )
    if out:
        print()
        print("=" * 60)
        print("  Telemetry dashboard rendered:")
        print(f"  {out}")
        print("=" * 60)
