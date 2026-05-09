"""Build charts + tables from the stats CSVs.

Also writes ``reports/telemetry_report.png``. Optional: open the PNG in a
pygame window (see ``python visualize.py --help``).

``main.py`` can call ``generate_report`` after a race with no window.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")  # no Tk needed; we draw with pygame if showing a window
import matplotlib.pyplot as plt
from matplotlib import patches
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle


# ---------------------------------------------------------------------------
# Constants & theme
# ---------------------------------------------------------------------------
PX_PER_FRAME_TO_PX_PER_SEC = 60.0

# Bold broadcast / timing UI: saturated accents on dark graphite.
COLORS = {
    "bg":         "#07080f",
    "panel":      "#0f1018",
    "panel_2":    "#151622",
    "panel_deep": "#0c0d12",
    "line":       "#32334a",
    "line_2":     "#45456a",
    "line_dim":   "#252538",
    "text":       "#ffffff",
    "text_2":     "#d2d6e6",
    "muted":      "#9aa3c0",
    "dim":        "#6d7690",
    "red":        "#ff1a1a",
    "red_soft":   "#ff6b6b",
    "red_glow":   "#ff4444",
    "gold":       "#ffcc00",
    "green":      "#00e676",
    "silver":     "#c8ced9",
    "bronze":     "#ff9f43",
    "cyan":       "#00e5ff",
    "purple":     "#b967ff",
    "pink":       "#ff5c9e",
    "orange":     "#ff9100",
    "grid":       "#353550",
    "chart_face": "#0a0c18",
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
# Typography (matplotlib uses the first font in the list that is installed)
# ---------------------------------------------------------------------------
_FONT_SANS_STACK = [
    "Inter",
    "Inter Variable",
    "Plus Jakarta Sans",
    "DM Sans",
    "IBM Plex Sans",
    "Segoe UI",
    "SF Pro Display",
    "SF Pro Text",
    ".SF NS Display",
    ".AppleSystemUIFont",
    "Helvetica Neue",
    "Helvetica",
    "Arial",
    "Liberation Sans",
    "DejaVu Sans",
]


def _typography_rc_params() -> dict:
    return {
        "font.family": "sans-serif",
        "font.sans-serif": _FONT_SANS_STACK,
        "font.size": 10,
        "font.weight": "normal",
        "axes.titleweight": "bold",
        "axes.labelweight": "bold",
        "figure.dpi": 115,
        "savefig.dpi": 115,
        "text.antialiased": True,
        "lines.antialiased": True,
        "patch.antialiased": True,
    }


# ---------------------------------------------------------------------------
# CSV load + pandas helpers
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

def _gap_series(gap_df: pd.DataFrame):
    if gap_df.empty or "timestamp" not in gap_df.columns:
        return np.array([]), np.array([])
    df = gap_df.copy()
    df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
    df["gap_progress"] = pd.to_numeric(df["gap_progress"], errors="coerce")
    df = df.dropna(subset=["timestamp", "gap_progress"])
    if df.empty:
        return np.array([]), np.array([])
    t0 = float(df["timestamp"].iloc[0])
    t = df["timestamp"].to_numpy(dtype=float) - t0
    g = df["gap_progress"].to_numpy(dtype=float)
    return t, g

def _position_arrays(pos_df: pd.DataFrame):
    if pos_df.empty:
        return np.array([]), np.array([]), np.array([])
    x = pd.to_numeric(pos_df.get("x"), errors="coerce")
    y = pd.to_numeric(pos_df.get("y"), errors="coerce")
    sp = pd.to_numeric(pos_df.get("speed_px_s"), errors="coerce")
    m = x.notna() & y.notna() & sp.notna()
    if not m.any():
        return np.array([]), np.array([]), np.array([])
    c = (sp[m].to_numpy(dtype=float) * PX_PER_FRAME_TO_PX_PER_SEC)
    return x[m].to_numpy(), y[m].to_numpy(), c

def _sector_means_for_table(sectors_df: pd.DataFrame) -> List[Tuple[str, str]]:
    rows = []
    if sectors_df.empty or "sector_index" not in sectors_df.columns:
        for seg in (1, 2, 3):
            rows.append((f"S{seg} mean", "--"))
        rows.append(("Beacons hit", "0"))
        return rows
    sp = pd.to_numeric(sectors_df["split_s"], errors="coerce")
    si = pd.to_numeric(sectors_df["sector_index"], errors="coerce")
    tmp = pd.DataFrame({"si": si, "sp": sp}).dropna()
    hit = len(tmp)
    for seg in (1, 2, 3):
        ss = tmp[tmp["si"] == seg]["sp"]
        rows.append((f"S{seg} mean (s)",
                     f"{float(ss.mean()):.2f}" if len(ss) else "--"))
    rows.append(("Beacons hit", f"{hit:,}"))
    return rows


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
    sectors_r: pd.DataFrame,
    positions_r: pd.DataFrame,
    gaps_r: pd.DataFrame,
    cornering_r: pd.DataFrame,
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

    gap_t, gap_g = _gap_series(gaps_r)
    pos_x, pos_y, pos_c = _position_arrays(positions_r)
    sector_table_rows = _sector_means_for_table(sectors_r)
    corner_n = int(len(cornering_r)) if not cornering_r.empty else 0

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
        "gap_t": gap_t,
        "gap_g": gap_g,
        "pos_x": pos_x,
        "pos_y": pos_y,
        "pos_c": pos_c,
        "sector_table_rows": sector_table_rows,
        "cornering_events": corner_n,
    }


# ---------------------------------------------------------------------------
# Layout (all heights in INCHES; total figure height = sum + gaps)
# ---------------------------------------------------------------------------
SECTION_HEIGHTS = {
    "top_margin":   0.30,
    "header":       1.00,
    "info_bar":     1.10,
    "coverage":     2.72,
    "kpi_row":      1.60,
    "sec1_head":    0.55,
    "stats_tbl":    2.55,
    "sec2_head":    0.55,
    "charts_r1":    2.80,
    "charts_r2":    2.80,
    "charts_r3":    2.65,
    "sec3_head":    0.55,
    "standings":    2.70,
    "footer":       0.45,
    "bottom_margin": 0.30,
}
SECTION_ORDER = [
    "top_margin", "header", "info_bar", "coverage", "kpi_row",
    "sec1_head", "stats_tbl",
    "sec2_head", "charts_r1", "charts_r2", "charts_r3",
    "sec3_head", "standings",
    "footer", "bottom_margin",
]
GAP_INCHES = 0.22
FIG_WIDTH = 18.2

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


def _track_speed_cmap():
    """Vivid trajectory heat: deep blue → cyan → lime → yellow → hot red."""
    return LinearSegmentedColormap.from_list(
        "track_spd",
        ["#0a0f2e", "#0044aa", "#00bcd4", "#76ff03", "#ffea00", "#ff1744",
         "#ff6d00"],
    )


def _hist_purple_cmap():
    return LinearSegmentedColormap.from_list(
        "hist_pri",
        ["#1a0a2e", "#5e00c4", COLORS["purple"], "#e040fb", "#f8b6ff"],
    )


def _coverage_row_groups(items: List) -> List[List]:
    """Split channel cards into rows for readable card height and width.

    Fewer cards per row = wider tiles; balanced row counts avoid one stub row.
    """
    n = len(items)
    if n <= 4:
        return [items]
    if n <= 8:
        mid = (n + 1) // 2
        return [items[:mid], items[mid:]]
    if n <= 12:
        nrows = 3
        base, rem = divmod(n, nrows)
        out, i = [], 0
        for r in range(nrows):
            take = base + (1 if r < rem else 0)
            out.append(items[i:i + take])
            i += take
        return out
    per = 4
    return [items[i:i + per] for i in range(0, n, per)]


def _axes_depth_gradient(ax, zorder: float = 0.5):
    """Panel sheen — visible but not flat."""
    arr = np.linspace(0, 1, 80, dtype=float).reshape(-1, 1)
    arr = np.repeat(arr, 200, axis=1)
    cmap = LinearSegmentedColormap.from_list(
        "panel_depth",
        [(0.0, "#080914"), (0.45, "#12152a"), (1.0, "#1c2040")],
    )
    ax.imshow(
        arr, extent=[0, 1, 0, 1], transform=ax.transAxes,
        aspect="auto", origin="upper", zorder=zorder,
        cmap=cmap, alpha=0.38, interpolation="bilinear",
    )


def _hide_axes(ax):
    ax.set_xticks([]); ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_facecolor("none")


def _panel_axes(fig, rect, facecolor=None, accent=None):
    """Minimal panel; optional left accent bar."""
    ax = fig.add_axes(rect)
    _hide_axes(ax); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    fc = facecolor or COLORS["panel"]
    ax.add_patch(Rectangle(
        (0, 0), 1, 1, transform=ax.transAxes,
        facecolor=fc,
        edgecolor=COLORS["line"], lw=0.4))
    if accent:
        ax.add_patch(Rectangle(
            (0, 0), 0.003, 1, transform=ax.transAxes,
            facecolor=accent, edgecolor="none", zorder=5))
    return ax

def _section_header(fig, rect, number: str, title: str, subtitle: str = ""):
    ax = fig.add_axes(rect)
    _hide_axes(ax); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.add_patch(Rectangle(
        (0, 0), 1, 1, transform=ax.transAxes,
        facecolor=COLORS["panel_2"], edgecolor="none", alpha=0.55,
        zorder=0))
    ax.plot([0.012, 0.012], [0.26, 0.74], color=COLORS["red"], lw=1.65,
            transform=ax.transAxes, solid_capstyle="butt", zorder=2)
    ax.add_patch(FancyBboxPatch(
        (0.022, 0.36), 0.036, 0.28, transform=ax.transAxes,
        boxstyle="round,pad=0,rounding_size=0.008",
        facecolor=COLORS["panel"], edgecolor=COLORS["line"],
        lw=0.35, zorder=1))
    ax.text(0.040, 0.50, number, transform=ax.transAxes,
            ha="center", va="center",
            color=COLORS["text_2"], fontsize=10.5, fontweight="bold",
            zorder=2)
    ax.text(0.068, 0.58, title, transform=ax.transAxes,
            ha="left", va="center",
            color=COLORS["text"], fontsize=13.2, fontweight="bold",
            zorder=2)
    if subtitle:
        ax.text(0.068, 0.34, subtitle, transform=ax.transAxes,
                ha="left", va="center",
                color=COLORS["muted"], fontsize=8.4, fontweight="bold",
                zorder=2)
    ax.plot([0.265, 0.995], [0.50, 0.50],
            color=COLORS["line"], lw=0.42, transform=ax.transAxes, zorder=2)

def _draw_header(fig, rect, payload):
    x, y, w, h = rect
    ax = fig.add_axes(rect)
    _hide_axes(ax); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_facecolor(COLORS["panel"])
    ax.add_patch(Rectangle(
        (0, 0), 1, 1, transform=ax.transAxes,
        facecolor=COLORS["panel"], edgecolor=COLORS["line"], lw=0.4,
        zorder=0))
    _axes_depth_gradient(ax, zorder=1)

    ax.plot([0, 1], [0.996, 0.996], color=COLORS["red"], lw=2.2,
            transform=ax.transAxes, clip_on=False, solid_capstyle="butt",
            zorder=4)

    ax.add_patch(Polygon(
        [(0.098, 0.20), (0.108, 0.78), (0.102, 0.78), (0.092, 0.20)],
        closed=True, transform=ax.transAxes,
        facecolor=COLORS["red"], edgecolor="none", alpha=0.78, zorder=2))

    ax.add_patch(FancyBboxPatch(
        (0.018, 0.24), 0.036, 0.52, transform=ax.transAxes,
        boxstyle="round,pad=0,rounding_size=0.014",
        facecolor=COLORS["red"], edgecolor="none", zorder=3))
    ax.text(0.036, 0.50, "F", transform=ax.transAxes,
            ha="center", va="center", color="#ffffff",
            fontsize=20, fontweight="bold", style="italic", zorder=4)
    ax.add_patch(FancyBboxPatch(
        (0.056, 0.24), 0.036, 0.52, transform=ax.transAxes,
        boxstyle="round,pad=0,rounding_size=0.014",
        facecolor="#e8e8ee", edgecolor=COLORS["line"], lw=0.35, zorder=3))
    ax.text(0.074, 0.50, "67", transform=ax.transAxes,
            ha="center", va="center", color=COLORS["bg"],
            fontsize=15, fontweight="bold", style="italic", zorder=4)

    ax.text(0.116, 0.595, "FORMULA 67", transform=ax.transAxes,
            ha="left", va="center",
            color=COLORS["text"], fontsize=20.5, fontweight="bold",
            style="italic", zorder=4)
    ax.text(0.116, 0.34, "Race control", transform=ax.transAxes,
            ha="left", va="center",
            color=COLORS["muted"], fontsize=9, fontweight="bold",
            zorder=4)
    ax.text(0.202, 0.34, "·", transform=ax.transAxes,
            ha="left", va="center", color=COLORS["dim"], fontsize=9,
            zorder=4)
    ax.text(0.212, 0.34, "Live timing & telemetry", transform=ax.transAxes,
            ha="left", va="center",
            color=COLORS["dim"], fontsize=9, fontweight="bold", zorder=4)

    ax.text(0.908, 0.62, "Session", transform=ax.transAxes,
            ha="right", va="center",
            color=COLORS["cyan"], fontsize=9, fontweight="bold",
            zorder=4)
    ax.text(0.908, 0.36, payload["generated_at"],
            transform=ax.transAxes, ha="right", va="center",
            color=COLORS["muted"], fontsize=9,
            family="monospace", fontweight="bold", zorder=4)

def _draw_info_bar(fig, rect, race):
    ax = fig.add_axes(rect)
    _hide_axes(ax); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_facecolor(COLORS["panel_2"])
    ax.add_patch(Rectangle(
        (0, 0), 1, 1, transform=ax.transAxes,
        facecolor=COLORS["panel_2"], edgecolor=COLORS["line"], lw=0.4,
        zorder=0))
    _axes_depth_gradient(ax, zorder=1)

    ax.plot([0, 1], [0.933, 0.933], color=COLORS["red"], lw=1.75,
            transform=ax.transAxes, clip_on=False, solid_capstyle="butt",
            zorder=3)

    winner = next((c for c in race["competitors"] if c.get("rank") == 1),
                  None)
    fastest = race["fastest"]

    cells = [
        ("ROUND",            f"{race['race_id']:02d}",
         "CURRENT SESSION",   COLORS["text"],   20),
        ("WINNER",
         (winner["name"].upper() if winner and winner.get("name") else "--"),
         (f"{winner['finish_time']:.2f} s · race"
          if winner and winner.get("finish_time") else "--"),
         COLORS["gold"], 16),
        ("FASTEST LAP",
         (fastest["name"].upper() if fastest and fastest.get("name") else "--"),
         (f"{fastest['best_lap']:.3f} s"
          if fastest and fastest.get("best_lap") is not None else "--"),
         COLORS["text"], 16),
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

        ax.plot([x_cursor + w - 0.001, x_cursor + w - 0.001],
                [0.11, 0.92], transform=ax.transAxes,
                color=COLORS["line_dim"], lw=0.48)
        ax.text(x_cursor + 0.016, 0.79, label, transform=ax.transAxes,
                ha="left", va="center", color=COLORS["muted"],
                fontsize=8.6, fontweight="bold")
        ax.text(x_cursor + 0.016, 0.49, value, transform=ax.transAxes,
                ha="left", va="center", color=color,
                fontsize=vfs, fontweight="bold")
        ax.text(x_cursor + 0.016, 0.21, sub, transform=ax.transAxes,
                ha="left", va="center", color=COLORS["dim"],
                fontsize=7.7, fontweight="bold")
        x_cursor += w

def _draw_coverage(fig, rect, coverage):
    ax = fig.add_axes(rect)
    _hide_axes(ax); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_facecolor(COLORS["panel"])
    ax.add_patch(Rectangle(
        (0, 0), 1, 1, transform=ax.transAxes,
        facecolor=COLORS["panel"], edgecolor=COLORS["line"], lw=0.4,
        zorder=0))
    _axes_depth_gradient(ax, zorder=1)

    ax.plot([0.01, 0.99], [0.993, 0.993], color=COLORS["red"], lw=1.65,
            transform=ax.transAxes, clip_on=True, solid_capstyle="butt",
            zorder=4)

    n_ch = len(coverage)
    item_rows = _coverage_row_groups(coverage)
    nrows = len(item_rows)

    y_grid_top = 0.815
    ax.plot([0.032, 0.032], [0.805, 0.985], color=COLORS["cyan"], lw=1.35,
            transform=ax.transAxes, solid_capstyle="butt", zorder=6)
    ax.text(0.048, 0.965, "Telemetry channels", transform=ax.transAxes,
            ha="left", va="top", color=COLORS["text"],
            fontsize=12.5, fontweight="bold", zorder=6)
    ax.text(0.048, 0.888, f"{n_ch} channels  ·  session export",
            transform=ax.transAxes, ha="left", va="top",
            color=COLORS["cyan"], fontsize=9.1, fontweight="bold",
            zorder=6)
    ax.plot([0.044, 0.97], [y_grid_top, y_grid_top], color=COLORS["purple"],
            lw=0.65, transform=ax.transAxes, clip_on=True, zorder=5)

    x0 = 0.052
    gap = 0.01
    right_pad = 0.03
    bottom_margin = 0.038
    usable_h = y_grid_top - bottom_margin
    gap_between = 0.036

    if nrows == 1:
        h = min(0.78, max(0.22, usable_h - 0.008))
        row_yhs = [(bottom_margin, h)]
    elif nrows == 2:
        h = max(0.20, (usable_h - gap_between) / 2)
        row_yhs = [
            (bottom_margin + h + gap_between, h),
            (bottom_margin, h),
        ]
    else:
        h = max(0.17, (usable_h - 2 * gap_between) / 3)
        row_yhs = [
            (bottom_margin + 2 * (h + gap_between), h),
            (bottom_margin + h + gap_between, h),
            (bottom_margin, h),
        ]

    for row_idx, items in enumerate(item_rows):
        if row_idx >= len(row_yhs):
            break
        y0, h = row_yhs[row_idx]
        if y0 + h > y_grid_top + 1e-4:
            h = max(0.12, y_grid_top - y0)
        nc = len(items)
        if nc == 0:
            continue
        avail = 1.0 - x0 - right_pad - gap * max(0, nc - 1)
        w = max(0.058, avail / nc)
        w = min(w, 0.228)
        fs_count = min(17, max(9, int(165 / max(nc, 1))))
        fs_label = min(8.6, max(7.0, int(50 / max(nc, 1))))

        for i, item in enumerate(items):
            x = x0 + i * (w + gap)
            w_cell = w
            if x + w_cell > 1.0 - right_pad:
                w_cell = max(0.048, 1.0 - right_pad - x)
            count = item["count"]
            color = item["color"]
            ok = count >= 100
            half = count >= 50
            badge_fill = (COLORS["green"] if ok
                          else (COLORS["gold"] if half else COLORS["red"]))
            badge_text = "PASS" if ok else f"{count}/100"

            pad = min(0.009, max(0.0035, w_cell * 0.048))
            cx = x + pad
            cy0 = y0 + pad * 0.55
            cw = max(w_cell - 2 * pad, w_cell * 0.84)
            ch = max(h - pad * 1.25, h * 0.92)
            accent_w = max(0.012, min(0.034, cw * 0.11))

            ax.add_patch(FancyBboxPatch(
                (cx, cy0), cw, ch, transform=ax.transAxes,
                boxstyle="round,pad=0,rounding_size=0.013",
                facecolor="#0d0f1c", edgecolor=COLORS["line_2"],
                lw=0.55, zorder=2))
            ax.add_patch(Rectangle(
                (cx, cy0), accent_w, ch,
                transform=ax.transAxes,
                facecolor=color, edgecolor="none", alpha=0.96, zorder=3))
            ax.plot([cx + accent_w, cx + accent_w], [cy0, cy0 + ch],
                    color=color, lw=1.1, alpha=0.9, transform=ax.transAxes,
                    zorder=4)

            pad_in = max(0.005, cw * 0.035)
            ix = cx + accent_w + pad_in
            iw = cw - accent_w - pad_in * 1.4

            ax.text(
                ix, cy0 + ch * 0.895,
                item["label"].upper(),
                transform=ax.transAxes, ha="left", va="center",
                color=color, fontsize=fs_label,
                fontweight="bold", zorder=5)

            body_lo = cy0 + ch * 0.12
            body_hi = cy0 + ch * 0.78
            body_h = max(1e-6, body_hi - body_lo)
            bh = min(0.072, max(0.042, body_h * 0.2))
            by = cy0 + ch * 0.1
            gap_nb = body_h * 0.1
            y_badge_top = by + bh
            y_hi_num = body_hi - gap_nb
            y_lo_num = y_badge_top + gap_nb
            if y_hi_num > y_lo_num:
                mid_y = 0.5 * (y_lo_num + y_hi_num)
            else:
                mid_y = body_lo + body_h * 0.5

            ax.text(ix + iw * 0.5, mid_y, f"{count:,}",
                    transform=ax.transAxes, ha="center", va="center",
                    color=COLORS["text"], fontsize=fs_count,
                    fontweight="bold", zorder=5)

            badge_w = min(0.092, max(0.05, iw * 0.72))
            bx = ix + (iw - badge_w) / 2
            ax.add_patch(FancyBboxPatch(
                (bx, by), badge_w, bh, transform=ax.transAxes,
                boxstyle="round,pad=0,rounding_size=0.01",
                facecolor=badge_fill, edgecolor=COLORS["text"],
                lw=0.55, alpha=1.0, zorder=4))
            btcol = "#052018" if ok else "#1f0808"
            ax.text(bx + badge_w / 2, by + bh / 2, badge_text,
                    transform=ax.transAxes, ha="center", va="center",
                    color=btcol, fontsize=8.0, fontweight="bold", zorder=5)

def _draw_kpi_row(fig, rect, race):
    x, y, w_total, h_total = rect
    s = race["summary"]
    lap_avg = race["lap_stats"]["mean"]
    delta = (s["best_lap"] - lap_avg) if lap_avg > 0 else 0
    kpis = [
        ("RACE TIME",   f"{s['total_time']:.2f}", "s",
         f"{race['lap_count']} laps", COLORS["red"]),
        ("FASTEST LAP", f"{s['best_lap']:.2f}", "s",
         (f"{delta:+.2f} s vs avg lap" if lap_avg > 0 else "personal best"),
         COLORS["text_2"]),
        ("AVG SPEED",   f"{race['speed_stats']['mean']:.1f}", "px/s",
         f"{race['speed_stats']['samples']:,} samples",
         COLORS["cyan"]),
        ("TOP SPEED",   f"{s['max_speed_px_s']:.1f}", "px/s",
         "peak", COLORS["gold"]),
        ("INCIDENTS",   f"{s['collisions']}", "",
         "clean session" if s["collisions"] == 0 else "contacts",
         COLORS["text"]),
        ("BOOST", f"{s['nitro_duration']:.1f}", "s",
         "nitro time", COLORS["green"]),
        ("CORNERING", f"{race.get('cornering_events', 0)}", "",
         "fast steer events", COLORS["pink"]),
    ]
    gap_fig = 0.007
    w_fig = (w_total - gap_fig * (len(kpis) - 1)) / len(kpis)
    for i, (label, val, unit, sub, c) in enumerate(kpis):
        rx = x + i * (w_fig + gap_fig)
        ax = fig.add_axes([rx, y, w_fig, h_total])
        _hide_axes(ax); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
        ax.add_patch(Rectangle(
            (0, 0), 1, 1, transform=ax.transAxes,
            facecolor=COLORS["panel_2"], edgecolor=COLORS["line"], lw=0.38,
            zorder=0))
        _axes_depth_gradient(ax, zorder=1)
        ax.plot([0.055, 0.945], [0.879, 0.879], color="#000000",
                lw=3.2, alpha=0.55, transform=ax.transAxes, clip_on=False,
                solid_capstyle="butt", zorder=2)
        ax.plot([0.055, 0.945], [0.882, 0.882], color=c, lw=2.35,
                transform=ax.transAxes, clip_on=False,
                solid_capstyle="butt", zorder=3)

        ax.text(0.08, 0.78, label, transform=ax.transAxes,
                ha="left", va="center", color=c,
                fontsize=8.8, fontweight="bold", zorder=4)

        ax.text(0.08, 0.47, val, transform=ax.transAxes,
                ha="left", va="center", color=COLORS["text"],
                fontsize=26, fontweight="bold", zorder=4)
        if unit:
            ax.text(0.92, 0.47, unit, transform=ax.transAxes,
                    ha="right", va="center", color=c,
                    fontsize=10, fontweight="bold", zorder=4)

        ax.text(0.08, 0.14, sub, transform=ax.transAxes,
                ha="left", va="center", color=COLORS["muted"],
                fontsize=7.8, fontweight="bold", zorder=4)

def _draw_stats_tables(fig, rect, race):
    x, y, w_total, h_total = rect
    gap_fig = 0.010
    n_cards = 4
    w_fig = (w_total - gap_fig * (n_cards - 1)) / n_cards
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
        ("SECTORS", COLORS["green"], "Split Beacons",
         "mean seconds to reach each checkpoint ring",
         race.get("sector_table_rows", [
             ("S1 mean", "--"), ("S2 mean", "--"), ("S3 mean", "--"),
             ("Beacons", "0")])),
    ]
    for i, (tag, color, title, sub, rows) in enumerate(cards):
        rx = x + i * (w_fig + gap_fig)
        ax = fig.add_axes([rx, y, w_fig, h_total])
        _hide_axes(ax); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
        ax.add_patch(FancyBboxPatch(
            (0.004, 0.004), 0.992, 0.992, transform=ax.transAxes,
            boxstyle="round,pad=0,rounding_size=0.018",
            facecolor=COLORS["panel"], edgecolor=COLORS["line"],
            lw=0.4, zorder=0))
        _axes_depth_gradient(ax, zorder=1)
        ax.plot([0.042, 0.958], [0.946, 0.946], color=color, lw=2.15,
                transform=ax.transAxes, clip_on=False,
                solid_capstyle="butt", zorder=2)

        ax.text(0.04, 0.88, tag, transform=ax.transAxes,
                ha="left", va="center", color=color,
                fontsize=8.4, fontweight="bold", zorder=3)
        ax.text(0.04, 0.805, title, transform=ax.transAxes,
                ha="left", va="center", color=COLORS["text"],
                fontsize=11.8, fontweight="bold", zorder=3)
        ax.text(0.04, 0.728, sub.title(), transform=ax.transAxes,
                ha="left", va="center", color=COLORS["muted"],
                fontsize=8.1, fontweight="bold", zorder=3)
        ax.plot([0.04, 0.96], [0.688, 0.688], color=COLORS["line"],
                lw=0.38, transform=ax.transAxes, zorder=2)

        y_top = 0.61
        y_bot = 0.08
        dy = (y_top - y_bot) / max(len(rows), 1)
        for j, (k, v) in enumerate(rows):
            yi = y_top - dy * (j + 0.5)
            ax.text(0.045, yi, k, transform=ax.transAxes, ha="left",
                    va="center", color=COLORS["text_2"], fontsize=10,
                    fontweight="bold", zorder=3)
            ax.text(0.955, yi, v, transform=ax.transAxes, ha="right",
                    va="center", color=COLORS["text"], fontsize=10,
                    fontweight="bold", family="monospace", zorder=3)
            if j < len(rows) - 1:
                ax.plot([0.045, 0.955],
                        [yi - dy * 0.5, yi - dy * 0.5],
                        color=COLORS["line_dim"], lw=0.38,
                        transform=ax.transAxes, zorder=2)

def _style_chart_ax(ax, xlabel, ylabel):
    ax.set_facecolor(COLORS["chart_face"])
    for spine in ax.spines.values():
        spine.set_edgecolor(COLORS["line_2"])
        spine.set_linewidth(0.55)
    ax.tick_params(colors=COLORS["text_2"], which="both",
                   labelsize=9.5, length=0, pad=5)
    ax.grid(True, color=COLORS["grid"], lw=0.52, alpha=0.42,
            linestyle="-")
    ax.set_axisbelow(True)
    ax.set_xlabel(xlabel.upper(), color=COLORS["muted"], fontsize=9.5,
                  fontweight="bold", labelpad=8)
    ax.set_ylabel(ylabel.upper(), color=COLORS["muted"], fontsize=9.5,
                  fontweight="bold", labelpad=8)

def _draw_chart_card(fig, rect, tag, color, title, sub):
    """Draw a chart card frame and return the inner (chart axes, inner rect)."""
    x, y, w, h = rect
    ax = fig.add_axes(rect)
    _hide_axes(ax); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_facecolor(COLORS["panel"])
    ax.add_patch(FancyBboxPatch(
        (0.004, 0.004), 0.992, 0.992, transform=ax.transAxes,
        boxstyle="round,pad=0,rounding_size=0.016",
        facecolor=COLORS["panel"], edgecolor=COLORS["line"],
        lw=0.4, zorder=0))
    _axes_depth_gradient(ax, zorder=1)
    ax.plot([0.025, 0.975], [0.948, 0.948], color=color, lw=2.0,
            transform=ax.transAxes, clip_on=False, solid_capstyle="butt",
            zorder=3)
    ax.text(0.04, 0.878, tag, transform=ax.transAxes,
            ha="left", va="center", color=color,
            fontsize=8.2, fontweight="bold", zorder=4)
    ax.text(0.04, 0.812, title, transform=ax.transAxes,
            ha="left", va="center", color=COLORS["text"],
            fontsize=11.4, fontweight="bold", zorder=4)
    ax.text(0.04, 0.758, sub.title(), transform=ax.transAxes,
            ha="left", va="center", color=COLORS["muted"],
            fontsize=8.1, fontweight="bold", zorder=4)

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
                            color=COLORS["red"], alpha=0.38, linewidth=0)
            c1.plot(t, s, color=COLORS["red_soft"], lw=1.9)
            c1.set_xlim(float(t.min()), float(t.max()))

        c2 = _draw_chart_card(fig, right_rect,
                              "DISTRIBUTION", COLORS["purple"],
                              "Speed Distribution",
                              "frequency across speed bins")
        _style_chart_ax(c2, "speed range (px/s)", "frequency")
        samples = race["speed_samples"]
        if len(samples) > 0:
            n_hist, _bins, patches = c2.hist(
                samples, bins=18, edgecolor=COLORS["chart_face"],
                linewidth=0.55, alpha=0.98)
            cm = _hist_purple_cmap()
            n_pat = len(patches)
            for hi, p in enumerate(patches):
                p.set_facecolor(cm(hi / max(n_pat - 1, 1)))
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
                c3.scatter(others["x"], others["y"], s=28,
                           color=COLORS["green"], alpha=0.88,
                           edgecolors=COLORS["cyan"], linewidths=0.45,
                           label=f"other races ({len(others)})")
            if not mine.empty:
                c3.scatter(mine["x"], mine["y"], s=72,
                           color=COLORS["red"],
                           edgecolors=COLORS["text"], linewidths=1.15,
                           label=f"this race ({len(mine)})", zorder=5)
            leg = c3.legend(
                loc="upper right", fontsize=8.5, frameon=True, borderpad=0.5,
                fancybox=True, framealpha=0.94,
                facecolor=COLORS["panel"], edgecolor=COLORS["line_2"])
            if leg is not None:
                for t in leg.get_texts():
                    t.set_color(COLORS["text_2"])

        x4, y4, w4, h4 = right_rect
        _panel_axes(fig, right_rect, facecolor=COLORS["panel"],
                    accent=COLORS["gold"])

        frame = fig.axes[-1]
        _axes_depth_gradient(frame, zorder=0.45)
        frame.plot([0.02, 0.98], [0.948, 0.948], color=COLORS["gold"], lw=1.85,
                   transform=frame.transAxes, clip_on=False, zorder=4)
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
        c4.set_facecolor(COLORS["chart_face"])
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

def _draw_charts_row3(fig, row_rect, race):
    x, y, w, h = row_rect
    gap_fig = 0.012
    col_w = (w - gap_fig) / 2
    left_rect = (x, y, col_w, h)
    right_rect = (x + col_w + gap_fig, y, col_w, h)
    c1 = _draw_chart_card(fig, left_rect,
                          "TRAJECTORY", COLORS["cyan"],
                          "Car XY path",
                          "colour = speed (px/s)")
    _style_chart_ax(c1, "x (px)", "y (px)")
    px, py, pc = race["pos_x"], race["pos_y"], race["pos_c"]
    if len(px) > 1:
        vmin, vmax = float(np.min(pc)), float(np.max(pc))
        if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax <= vmin:
            vmax = vmin + 1e-6
        sc = c1.scatter(
            px, py, c=pc, s=22, cmap=_track_speed_cmap(),
            vmin=vmin, vmax=vmax,
            alpha=0.94, edgecolors="none")
        cb = fig.colorbar(sc, ax=c1, fraction=0.046, pad=0.02)
        cb.ax.tick_params(colors=COLORS["text_2"], labelsize=7.5, length=2,
                          width=0.6)
        cb.ax.yaxis.label.set(color=COLORS["muted"])
        cb.outline.set_edgecolor(COLORS["line_2"])
        cb.outline.set_linewidth(0.55)

    c2 = _draw_chart_card(fig, right_rect,
                          "GAP", COLORS["orange"],
                          "Distance to leader",
                          "path progress units (higher = behind)")
    _style_chart_ax(c2, "time (s)", "gap")
    gt, gg = race["gap_t"], race["gap_g"]
    if len(gt) > 0:
        c2.plot(gt, gg, color=COLORS["orange"], lw=1.95)
        c2.axhline(0, color=COLORS["muted"], lw=0.9, ls="--", alpha=0.8)
        c2.set_xlim(float(gt.min()), float(gt.max()))


def _draw_standings(fig, rect, race):
    ax = _panel_axes(fig, rect, facecolor=COLORS["panel"])
    _axes_depth_gradient(ax, zorder=0.45)
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
    ax.plot([0.02, 0.98], [0.852, 0.852], color=COLORS["line"],
            lw=0.45, transform=ax.transAxes)

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
                color=pill_text_color, fontsize=10.5, fontweight="normal",
                )

        dc = _driver_color(name)
        ax.add_patch(patches.Circle(
            (col_xs[1] + 0.010, y_c), 0.008,
            transform=ax.transAxes,
            facecolor=dc, edgecolor="#000", lw=0.8))

        name_color = COLORS["gold"] if rank == 1 else COLORS["text"]
        ax.text(col_xs[2], y_c, name.upper(),
                transform=ax.transAxes, ha="left", va="center",
                color=name_color, fontsize=10.4, fontweight="bold")

        bl_txt = f"{bl:.2f}s" if bl is not None else "--"
        ft_txt = f"{ft:.2f}s" if ft is not None else "DNF"
        ax.text(col_xs[3], y_c, bl_txt, transform=ax.transAxes,
                ha="right", va="center", color=COLORS["text"],
                fontsize=9.9, family="monospace", fontweight="bold")
        ax.text(col_xs[4], y_c, ft_txt, transform=ax.transAxes,
                ha="right", va="center", color=COLORS["text"],
                fontsize=9.9, family="monospace", fontweight="bold")

        if rank == 1:
            ax.add_patch(Rectangle(
                (col_xs[5] - 0.060, y_c - row_h * 0.22),
                0.060, row_h * 0.44,
                transform=ax.transAxes,
                facecolor=COLORS["red"], edgecolor="none"))
            ax.text(col_xs[5] - 0.030, y_c, "Leader",
                    transform=ax.transAxes, ha="center", va="center",
                    color="#fff", fontsize=7.8, fontweight="normal")
        elif ft is not None and winner_time is not None:
            gap = ft - winner_time
            ax.text(col_xs[5], y_c, f"+{gap:.3f}",
                    transform=ax.transAxes, ha="right", va="center",
                    color=COLORS["text_2"], fontsize=10,
                    family="monospace", fontweight="bold")
        else:
            ax.text(col_xs[5], y_c, "--",
                    transform=ax.transAxes, ha="right", va="center",
                    color=COLORS["dim"], fontsize=10,
                    family="monospace", fontweight="bold")

        ax.text(col_xs[6], y_c, str(laps),
                transform=ax.transAxes, ha="right", va="center",
                color=COLORS["text"], fontsize=9.9,
                family="monospace", fontweight="bold")

def _draw_footer(fig, rect):
    x, y, w, h = rect
    ax = fig.add_axes(rect)
    _hide_axes(ax); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_facecolor(COLORS["bg"])
    ax.plot([0, 1], [0.95, 0.95], color=COLORS["line"], lw=0.42,
            transform=ax.transAxes)
    ax.text(0.02, 0.48, "Formula 67  ·  telemetry export",
            transform=ax.transAxes, ha="left", va="center",
            color=COLORS["muted"], fontsize=8.6, fontweight="bold")
    ax.text(0.98, 0.48,
            "Units · speed px/s · time s",
            transform=ax.transAxes, ha="right", va="center",
            color=COLORS["dim"], fontsize=8.2, fontweight="bold")


# ---------------------------------------------------------------------------
# Figure composition
# ---------------------------------------------------------------------------
def _render_dashboard(payload, race, coverage):
    """Build the full matplotlib figure and return (fig, total_height)."""
    rects, total_in = _compute_layout()

    plt.rcParams.update(_typography_rc_params())
    plt.rcParams.update({
        "axes.edgecolor": COLORS["line"],
        "axes.linewidth": 0.55,
        "axes.labelcolor": COLORS["muted"],
        "xtick.color": COLORS["muted"],
        "ytick.color": COLORS["muted"],
    })

    fig = plt.figure(figsize=(FIG_WIDTH, total_in))
    fig.patch.set_facecolor(COLORS["bg"])

    margin_x = 0.02

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
    _draw_charts_row3(fig, R("charts_r3"), race)
    _section_header(fig, R("sec3_head"), "03",
                    "Race Classification", "// final result")
    _draw_standings(fig, R("standings"), race)
    _draw_footer(fig, R("footer"))
    return fig, total_in


# ---------------------------------------------------------------------------
# Pygame-based PNG viewer (Tk from python.org/pyenv broke on newer macOS)
# ---------------------------------------------------------------------------
class EmbeddedTelemetryViewer:
    """Pan/zoom the big telemetry PNG inside the game window."""

    TOP_BAR = 44

    def __init__(
            self,
            png_path: str,
            race_ids: List[int],
            current_race: int,
            render_fn: Callable[[int], Optional[str]],
            *,
            standalone: bool = False,
    ):
        import pygame
        self._pg = pygame
        self.png_path = png_path
        self.race_ids = list(sorted(race_ids))
        self.current_race = int(current_race)
        self.render_fn = render_fn
        self.standalone = standalone
        self.scroll_x = 0
        self.scroll_y = 0
        self.dragging = False
        self.drag_from = (0, 0)
        self.drag_scroll = (0, 0)
        self.prev_rect = pygame.Rect(0, 0, 0, 0)
        self.next_rect = pygame.Rect(0, 0, 0, 0)
        self.back_rect = pygame.Rect(0, 0, 0, 0)
        self.bg = (9, 9, 14)
        self._reload_image()

    def _reload_image(self):
        self.img = self._pg.image.load(self.png_path)
        self.img_w, self.img_h = self.img.get_size()

    def _font(self, size: int, bold: bool = True, mono: bool = False):
        try:
            fams = ("Menlo,Consolas,Courier New,monospace" if mono
                    else "Inter,Plus Jakarta Sans,Segoe UI,Helvetica Neue,"
                         "Arial,Helvetica,sans-serif")
            return self._pg.font.SysFont(fams, size, bold=bold)
        except Exception:
            return self._pg.font.Font(None, size + 2)

    def _max_scroll(self, win_w: int, win_h: int):
        view_h = max(1, win_h - self.TOP_BAR)
        max_x = max(0, self.img_w - win_w)
        max_y = max(0, self.img_h - view_h)
        return max_x, max_y

    def _clamp_scroll(self, win_w: int, win_h: int):
        max_x, max_y = self._max_scroll(win_w, win_h)
        self.scroll_x = max(0, min(max_x, self.scroll_x))
        self.scroll_y = max(0, min(max_y, self.scroll_y))

    def _switch_race(self, delta: int):
        if not self.race_ids:
            return
        try:
            idx = self.race_ids.index(self.current_race)
        except ValueError:
            idx = len(self.race_ids) - 1
        new_idx = max(0, min(len(self.race_ids) - 1, idx + delta))
        if self.race_ids[new_idx] == self.current_race:
            return
        new_rid = self.race_ids[new_idx]
        if self.render_fn(new_rid):
            self._reload_image()
            self.current_race = new_rid
            self.scroll_y = 0

    def handle_event(self, event) -> Optional[str]:
        """Return "pop" when the user backs out to the menu/results."""
        pygame = self._pg
        if event.type == pygame.QUIT:
            return None
        surf = pygame.display.get_surface()
        if surf is None:
            return None
        win_w, win_h = surf.get_size()
        step = 60
        page = max(1, (win_h - self.TOP_BAR) - 80)

        if event.type == pygame.VIDEORESIZE and self.standalone:
            pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F11:
                pygame.display.toggle_fullscreen()
                return None
            if event.key in (pygame.K_ESCAPE, pygame.K_q, pygame.K_BACKSPACE):
                return "pop"
            if event.key == pygame.K_LEFT:
                self._switch_race(-1)
            elif event.key == pygame.K_RIGHT:
                self._switch_race(1)
            elif event.key == pygame.K_DOWN:
                self.scroll_y += step
            elif event.key == pygame.K_UP:
                self.scroll_y -= step
            elif event.key in (pygame.K_PAGEDOWN, pygame.K_SPACE):
                self.scroll_y += page
            elif event.key == pygame.K_PAGEUP:
                self.scroll_y -= page
            elif event.key == pygame.K_HOME:
                self.scroll_y = 0
            elif event.key == pygame.K_END:
                self.scroll_y = self.img_h
        elif event.type == pygame.MOUSEWHEEL:
            if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                self.scroll_x -= event.y * 60
            else:
                self.scroll_y -= event.y * 60
            self.scroll_x -= getattr(event, "x", 0) * 60
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            if self.back_rect.collidepoint(pos):
                return "pop"
            if self.prev_rect.collidepoint(pos):
                self._switch_race(-1)
            elif self.next_rect.collidepoint(pos):
                self._switch_race(1)
            elif pos[1] > self.TOP_BAR:
                self.dragging = True
                self.drag_from = pos
                self.drag_scroll = (self.scroll_x, self.scroll_y)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            mx, my = event.pos
            self.scroll_x = self.drag_scroll[0] + (self.drag_from[0] - mx)
            self.scroll_y = self.drag_scroll[1] + (self.drag_from[1] - my)

        self._clamp_scroll(win_w, win_h)
        return None

    def _draw_top_bar(self, target: "pygame.Surface", win_w: int, win_h: int):
        pygame = self._pg
        TOP_BAR = self.TOP_BAR
        bar = pygame.Surface((win_w, TOP_BAR), pygame.SRCALPHA)
        bar.fill((15, 15, 22, 250))
        pygame.draw.rect(bar, (225, 6, 0), (0, TOP_BAR - 1, win_w, 1))

        f_label = self._font(9, bold=True)
        f_big = self._font(18, bold=True)
        f_tip = self._font(10, bold=True, mono=True)

        bf = self._font(13, bold=True)
        back_txt = bf.render("BACK", True, (255, 255, 255))
        pad_x = 10
        self.back_rect = pygame.Rect(
            8, (TOP_BAR - back_txt.get_height() - 8) // 2,
            back_txt.get_width() + pad_x * 2, back_txt.get_height() + 8)
        pygame.draw.rect(bar, (30, 30, 40), self.back_rect, border_radius=6)
        pygame.draw.rect(bar, (70, 70, 82), self.back_rect, width=1,
                         border_radius=6)
        bar.blit(back_txt,
                 (self.back_rect.centerx - back_txt.get_width() // 2,
                  self.back_rect.centery - back_txt.get_height() // 2))

        bx = self.back_rect.right + 14
        brand = f_big.render("FORMULA 67", True, (230, 230, 235))
        bar.blit(brand, (bx, 10))
        acc = f_label.render("TELEMETRY", True, (150, 150, 165))
        bar.blit(acc, (bx + brand.get_width() + 12, 18))

        if self.race_ids:
            try:
                idx = self.race_ids.index(self.current_race)
            except ValueError:
                idx = len(self.race_ids) - 1
            total = len(self.race_ids)
            has_prev = idx > 0
            has_next = idx < total - 1

            label_txt = f_label.render("ROUND", True, (150, 150, 165))
            value_txt = f_big.render(
                f"{self.current_race:02d}", True, (255, 220, 80))
            meta_txt = f_tip.render(f"{idx + 1} / {total}",
                                    True, (140, 140, 155))

            arrow_size = 26
            gap = 10
            group_w = (arrow_size + gap + label_txt.get_width() + 6
                       + value_txt.get_width() + gap
                       + meta_txt.get_width() + gap + arrow_size)
            group_x = max(self.back_rect.right + 8, (win_w - group_w) // 2)
            cy = TOP_BAR // 2

            self.prev_rect = pygame.Rect(group_x, cy - arrow_size // 2,
                                           arrow_size, arrow_size)
            prev_col = (225, 6, 0) if has_prev else (60, 60, 72)
            pygame.draw.rect(bar, prev_col, self.prev_rect, border_radius=6)
            pts = [(self.prev_rect.right - 9, self.prev_rect.top + 6),
                   (self.prev_rect.left + 9, self.prev_rect.centery),
                   (self.prev_rect.right - 9, self.prev_rect.bottom - 6)]
            pygame.draw.polygon(bar, (255, 255, 255), pts)

            lx = self.prev_rect.right + gap
            bar.blit(label_txt, (lx, cy - label_txt.get_height() // 2 - 2))
            lx += label_txt.get_width() + 6
            bar.blit(value_txt, (lx, cy - value_txt.get_height() // 2))
            lx += value_txt.get_width() + gap
            bar.blit(meta_txt, (lx, cy - meta_txt.get_height() // 2))
            lx += meta_txt.get_width() + gap

            self.next_rect = pygame.Rect(lx, cy - arrow_size // 2,
                                         arrow_size, arrow_size)
            next_col = (225, 6, 0) if has_next else (60, 60, 72)
            pygame.draw.rect(bar, next_col, self.next_rect, border_radius=6)
            pts = [(self.next_rect.left + 9, self.next_rect.top + 6),
                   (self.next_rect.right - 9, self.next_rect.centery),
                   (self.next_rect.left + 9, self.next_rect.bottom - 6)]
            pygame.draw.polygon(bar, (255, 255, 255), pts)
        else:
            self.prev_rect = pygame.Rect(0, 0, 0, 0)
            self.next_rect = pygame.Rect(0, 0, 0, 0)

        hint = ("← →  round   wheel  scroll   Esc  back" if not self.standalone
                else "← →  round   wheel  scroll   Esc  exit")
        hint_txt = f_tip.render(hint, True, (160, 160, 175))
        bar.blit(hint_txt,
                 (win_w - hint_txt.get_width() - 8,
                  TOP_BAR // 2 - hint_txt.get_height() // 2))

        target.blit(bar, (0, 0))

    def draw(self, surface) -> None:
        pygame = self._pg
        win_w, win_h = surface.get_size()
        self._clamp_scroll(win_w, win_h)
        surface.fill(self.bg)

        off_x = max(0, (win_w - self.img_w) // 2) - self.scroll_x
        off_y = self.TOP_BAR - self.scroll_y
        surface.blit(self.img, (off_x, off_y))

        _, max_y = self._max_scroll(win_w, win_h)
        if max_y > 0:
            view_h = win_h - self.TOP_BAR
            track_w = 8
            track_x = win_w - track_w - 2
            pygame.draw.rect(surface, (30, 30, 38),
                             (track_x, self.TOP_BAR, track_w, view_h))
            thumb_h = max(30, int(view_h * view_h / self.img_h))
            thumb_y = (self.TOP_BAR
                       + int((view_h - thumb_h) * self.scroll_y / max_y))
            pygame.draw.rect(surface, (225, 6, 0),
                             (track_x, thumb_y, track_w, thumb_h),
                             border_radius=3)

        self._draw_top_bar(surface, win_w, win_h)


def _show_in_pygame_window(
        png_path: str,
        title: str = "Formula 67 · Telemetry Dashboard",
        race_ids: Optional[List[int]] = None,
        current_race: Optional[int] = None,
        render_fn: Optional[Callable[[int], Optional[str]]] = None):
    """Standalone pygame window for the PNG + race switching."""
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

    rids = list(race_ids) if race_ids else []
    rids.sort()
    cur = current_race if current_race is not None else (
        rids[-1] if rids else 0)

    viewer = EmbeddedTelemetryViewer(
        png_path, rids, cur, render_fn or (lambda _r: None),
        standalone=True,
    )
    img_w, img_h = viewer.img_w, viewer.img_h

    info = pygame.display.Info()
    screen_w = info.current_w or 1600
    screen_h = info.current_h or 900
    win_w = min(img_w, max(900, screen_w - 120))
    win_h = min(img_h + EmbeddedTelemetryViewer.TOP_BAR,
                max(640, screen_h - 160))

    flags = pygame.RESIZABLE
    pygame.display.set_mode((win_w, win_h), flags)
    pygame.display.set_caption(title)

    clock = pygame.time.Clock()
    running = True
    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif viewer.handle_event(ev) == "pop":
                running = False
        screen = pygame.display.get_surface()
        viewer.draw(screen)
        pygame.display.flip()
        clock.tick(60)

    try:
        pygame.display.quit()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Public API + CLI
# ---------------------------------------------------------------------------
def _make_telemetry_render_bundle(
        stats_dir: str,
        out_dir: str,
        race_id: Optional[int] = None,
) -> Optional[Tuple[str, List[int], int, Callable[[int], Optional[str]]]]:
    if not os.path.isdir(stats_dir):
        print(f"[visualize] stats dir not found: {stats_dir}")
        return None

    race_summaries = _read_csv_df(os.path.join(stats_dir, "race_summary.csv"))
    laps = _read_csv_df(os.path.join(stats_dir, "lap_time.csv"))
    speeds = _read_csv_df(os.path.join(stats_dir, "speed.csv"))
    competitors = _read_csv_df(os.path.join(stats_dir, "competitor.csv"))
    nitros = _read_csv_df(os.path.join(stats_dir, "nitro.csv"))
    steerings = _read_csv_df(os.path.join(stats_dir, "steering.csv"))
    nitro_events = _read_csv_df(os.path.join(stats_dir, "nitro_event.csv"))
    collision_events = _read_csv_df(
        os.path.join(stats_dir, "collision_event.csv"))
    steering_events = _read_csv_df(
        os.path.join(stats_dir, "steering_event.csv"))
    position_df = _read_csv_df(os.path.join(stats_dir, "position.csv"))
    sector_df = _read_csv_df(os.path.join(stats_dir, "sector_split.csv"))
    gap_df = _read_csv_df(os.path.join(stats_dir, "gap_sample.csv"))
    input_df = _read_csv_df(os.path.join(stats_dir, "input_sample.csv"))
    corner_df = _read_csv_df(
        os.path.join(stats_dir, "cornering_event.csv"))

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

    coverage = [
        {"label": "Speed",       "count": int(len(speeds)),
         "color": COLORS["cyan"]},
        {"label": "Steering",    "count": int(len(steering_events)),
         "color": COLORS["pink"]},
        {"label": "Laps",        "count": int(len(laps)),
         "color": COLORS["gold"]},
        {"label": "Collisions",  "count": int(len(collision_events)),
         "color": COLORS["red"]},
        {"label": "Nitro",       "count": int(len(nitro_events)),
         "color": COLORS["green"]},
        {"label": "XY Path",     "count": int(len(position_df)),
         "color": COLORS["cyan"]},
        {"label": "Sectors",     "count": int(len(sector_df)),
         "color": COLORS["green"]},
        {"label": "Pedals",      "count": int(len(input_df)),
         "color": COLORS["orange"]},
        {"label": "Gap trace",   "count": int(len(gap_df)),
         "color": COLORS["orange"]},
        {"label": "Cornering",   "count": int(len(corner_df)),
         "color": COLORS["purple"]},
    ]

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "telemetry_report.png")

    def _render_to_png(rid: int) -> Optional[str]:
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
            sectors_r=_filter_race(sector_df, int(rid)),
            positions_r=_filter_race(position_df, int(rid)),
            gaps_r=_filter_race(gap_df, int(rid)),
            cornering_r=_filter_race(corner_df, int(rid)),
        )
        race_i["total_races"] = len(all_race_ids)
        payload_i = {
            "generated_at": datetime.now().strftime("%a %d %b %Y · %H:%M"),
            "default_race": int(rid),
            "coverage": coverage,
            "race": race_i,
        }
        fig_i, _ = _render_dashboard(payload_i, race_i, coverage)
        fig_i.savefig(out_path, facecolor=COLORS["bg"],
                      bbox_inches=None, pad_inches=0)
        plt.close(fig_i)
        return out_path

    _render_to_png(target_id)
    return out_path, all_race_ids, target_id, _render_to_png


def build_embedded_telemetry_viewer(
        stats_dir: str = "stats",
        out_dir: str = "reports",
        race_id: Optional[int] = None,
) -> Optional[EmbeddedTelemetryViewer]:
    """Wire up the in-game report viewer (or None if no PNG yet)."""
    bundle = _make_telemetry_render_bundle(stats_dir, out_dir, race_id)
    if bundle is None:
        return None
    out_path, all_race_ids, target_id, render_fn = bundle
    return EmbeddedTelemetryViewer(out_path, all_race_ids, target_id,
                                   render_fn, standalone=False)


def generate_report(stats_dir: str = "stats",
                    out_dir: str = "reports",
                    race_id: Optional[int] = None,
                    open_browser: bool = False,
                    show_window: bool = False) -> Optional[str]:
    """Save ``telemetry_report.png``; optionally open it in a pygame window
    (``show_window`` / legacy ``open_browser``)."""
    bundle = _make_telemetry_render_bundle(stats_dir, out_dir, race_id)
    if bundle is None:
        return None
    out_path, all_race_ids, target_id, render_fn = bundle
    want_window = show_window or open_browser
    if want_window:
        _show_in_pygame_window(
            out_path,
            title="Formula 67 · Telemetry Dashboard",
            race_ids=all_race_ids,
            current_race=target_id,
            render_fn=render_fn,
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
