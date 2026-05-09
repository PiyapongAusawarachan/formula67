#!/usr/bin/env python3
"""Spawns PDFs in ``docs/`` for the class hand-in (needs matplotlib)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def _page_text(fig, title, paragraphs):
    fig.clf()
    fig.text(0.08, 0.94, title, fontsize=14, fontweight="bold", va="top")
    y = 0.88
    for block in paragraphs:
        fig.text(
            0.08,
            y,
            block,
            fontsize=10,
            va="top",
            ha="left",
            wrap=True,
        )
        y -= 0.045 * (1 + block.count("\n"))


def build_proposal_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    intro = (
        "Formula 67 — Project proposal (v4.0)\n"
        "Author: Piyapong Ausawarachan\n"
        "Course: Computer Programming II — Software and Knowledge "
        "Engineering, Kasetsart University\n"
        "Document date: 6 March 2025 (content aligned with final codebase; "
        "PDF generated for submission packaging)."
    )

    p1 = (
        "Motivation: Many student racing prototypes implement movement and "
        "scoring only. Formula 67 extends a classic top-down racer with a "
        "telemetry layer so driving behaviour can be inspected after each "
        "session using tables and charts, mirroring real motorsports "
        "analytics at a small scale."
    )

    p2 = (
        "User story: A player selects a difficulty, completes a three-lap race "
        "against AI opponents on a fixed circuit, and receives immediate "
        "in-game feedback (HUD + results). Afterward, CSV logs capture speed "
        "samples, steering events, lap segments, collisions, and nitro bursts; "
        "a matplotlib script aggregates those logs into a single telemetry "
        "figure saved under reports/."
    )

    p3 = (
        "Technical scope: Python 3, pygame for rendering and interaction, "
        "mask collision for track limits and finish line, AABB tests for "
        "obstacles and nitro pads, and a RaceManager coordinating laps and "
        "timing. StatsLogger buffers structured rows and exports UTF-8 CSV "
        "files; Leaderboard persists the top ten lap times."
    )

    p4 = (
        "Data & visualization: At least five distinct features (speed time "
        "series, steering events, lap times, collisions, nitro-related "
        "metrics) are accumulated across races. visualize.py reads stats/*.csv "
        "and builds a multi-panel report containing tables, a line chart, "
        "histogram, scatter, and pie chart where applicable."
    )

    p5 = (
        "Development plan: (1) core OOP structure — Track, Car, RaceManager; "
        "(2) obstacle and nitro systems; (3) AI path followers; "
        "(4) StatsLogger integration; (5) matplotlib reporting; "
        "(6) polish, HUD, menus, documentation, and submission packaging."
    )

    p6 = (
        "Success criteria: Stable three-lap loop; demonstrable inheritance "
        "(PlayerCar extends Car); clear module boundaries; reproducible CSV "
        "export; generated visualization artefact; README and DESCRIPTION "
        "matching course outlines; LICENSE and attribution for external art."
    )

    with PdfPages(path) as pdf:
        fig = plt.figure(figsize=(8.5, 11))
        _page_text(
            fig,
            "Problem statement & objectives",
            [intro, "", p1, "", p2],
        )
        pdf.savefig(fig)
        _page_text(
            fig,
            "Scope, data pipeline, plan",
            [p3, "", p4, "", p5, "", p6],
        )
        pdf.savefig(fig)
        plt.close(fig)


def _build_uml_pdf_legacy(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(16.5, 11.7))
    ax.set_xlim(0, 16.5)
    ax.set_ylim(0, 11.7)
    ax.axis("off")
    ax.set_title(
        "Formula 67 - UML class diagram",
        fontsize=20,
        fontweight="bold",
        pad=18,
    )

    def uml_box(x, y, w, h, title, attrs, methods, color="#f7f9ff"):
        r = FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.025",
            linewidth=1.15,
            edgecolor="#1f2937",
            facecolor=color,
        )
        ax.add_patch(r)
        title_h = 0.42
        attr_h = max(0.28, h * 0.38)
        ax.plot([x, x + w], [y + h - title_h, y + h - title_h],
                color="#1f2937", linewidth=0.9)
        ax.plot([x, x + w], [y + h - title_h - attr_h,
                             y + h - title_h - attr_h],
                color="#1f2937", linewidth=0.8)
        ax.text(
            x + w / 2,
            y + h - 0.21,
            title,
            ha="center",
            va="center",
            fontsize=9,
            fontweight="bold",
            family="monospace",
        )
        ax.text(
            x + 0.12,
            y + h - title_h - 0.14,
            "\n".join(attrs),
            ha="left",
            va="top",
            fontsize=7.2,
            family="monospace",
            linespacing=1.18,
        )
        ax.text(
            x + 0.12,
            y + h - title_h - attr_h - 0.14,
            "\n".join(methods),
            ha="left",
            va="top",
            fontsize=7.2,
            family="monospace",
            linespacing=1.18,
        )

    def arrow(x1, y1, x2, y2, label=None, dashed=False, hollow=False):
        arrowstyle = "-|>" if not hollow else "Simple,tail_width=0.45,head_width=8,head_length=10"
        a = FancyArrowPatch(
            (x1, y1),
            (x2, y2),
            arrowstyle=arrowstyle,
            mutation_scale=10,
            linewidth=1.1,
            color="#374151",
            linestyle="--" if dashed else "-",
            shrinkA=4,
            shrinkB=4,
        )
        if hollow:
            a.set_facecolor("white")
        ax.add_patch(a)
        if label:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            ax.text(
                mx,
                my + 0.12,
                label,
                ha="center",
                fontsize=7,
                color="#374151",
                bbox=dict(facecolor="white", edgecolor="none", pad=1.5),
            )

    def elbow(points, label=None, dashed=False, hollow=False, label_index=None):
        xs, ys = zip(*points)
        ax.plot(
            xs,
            ys,
            color="#374151",
            linewidth=1.05,
            linestyle="--" if dashed else "-",
            solid_capstyle="round",
            zorder=-0.5,
        )
        arrowstyle = "-|>" if not hollow else "Simple,tail_width=0.45,head_width=8,head_length=10"
        a = FancyArrowPatch(
            points[-2],
            points[-1],
            arrowstyle=arrowstyle,
            mutation_scale=10,
            linewidth=1.05,
            color="#374151",
            linestyle="--" if dashed else "-",
            shrinkA=0,
            shrinkB=4,
            zorder=0,
        )
        if hollow:
            a.set_facecolor("white")
        ax.add_patch(a)
        if label:
            idx = label_index if label_index is not None else max(0, len(points) // 2 - 1)
            x1, y1 = points[idx]
            x2, y2 = points[idx + 1]
            ax.text(
                (x1 + x2) / 2,
                (y1 + y2) / 2 + 0.12,
                label,
                ha="center",
                fontsize=7,
                color="#374151",
                bbox=dict(facecolor="white", edgecolor="none", pad=1.7),
            )

    def module_box(x, y, w, h, title, subtitle):
        r = FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.04",
            linewidth=1.05,
            edgecolor="#334155",
            facecolor="#ffffff",
        )
        ax.add_patch(r)
        ax.text(
            x + w / 2,
            y + h * 0.62,
            title,
            ha="center",
            va="center",
            fontsize=8.5,
            fontweight="bold",
            family="monospace",
            color="#111827",
        )
        ax.text(
            x + w / 2,
            y + h * 0.28,
            subtitle,
            ha="center",
            va="center",
            fontsize=7,
            color="#475569",
        )

    def section(x, y, w, h, title):
        r = FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.04",
            linewidth=1,
            edgecolor="#cbd5e1",
            facecolor="#f8fafc",
            zorder=-2,
        )
        ax.add_patch(r)
        ax.text(x + 0.16, y + h - 0.28, title, fontsize=9,
                fontweight="bold", color="#475569")

    section(0.35, 6.25, 7.8, 4.55, "Race simulation")
    section(8.35, 6.25, 7.8, 4.55, "World objects")
    section(0.35, 1.0, 7.8, 4.75, "Telemetry and persistence")
    section(8.35, 1.0, 7.8, 4.75, "Presentation and analysis")

    uml_box(
        0.75, 8.75, 2.65, 1.65, "Car",
        ["+x, y: float", "+vel, angle: float", "+img: Surface"],
        ["+drive(forward, backward)", "+apply_friction()", "+check_collision(mask)", "+reset()"],
        "#eef6ff",
    )
    uml_box(
        0.75, 6.65, 2.65, 1.65, "PlayerCar",
        ["+nitro, nitro_max: float", "+nitro_active: bool", "+_last_safe_pos: tuple"],
        ["+add_nitro(seconds)", "+update_nitro(dt, requested)", "+bounce_off_wall(track)", "+reset()"],
        "#e0f2fe",
    )
    uml_box(
        4.35, 8.55, 3.05, 1.85, "RaceManager",
        ["+TOTAL_LAPS: int", "+current_lap: int", "+lap_times: list", "+player_finished: bool"],
        ["+start_race()", "+track_lap_time()", "+race_summary()", "+reset_game()"],
        "#fef9c3",
    )
    uml_box(
        4.35, 6.55, 3.05, 1.65, "AIRacer",
        ["+name: str", "+personal_path: list", "+lap_times: list", "+finish_time: float"],
        ["+update(total_laps)", "+progress_score()", "+best_lap_time()", "+draw(win)"],
        "#f5f3ff",
    )

    uml_box(
        8.8, 8.72, 2.85, 1.68, "Track",
        ["+border_mask: Mask", "+finish_mask: Mask", "+checkpoints: list"],
        ["+is_out_of_bounds(car)", "+at_finish_line(car)", "+draw(win)", "+get_track_path()"],
        "#ecfdf5",
    )
    uml_box(
        12.25, 8.72, 2.95, 1.68, "Obstacle",
        ["+position: tuple", "+type: str", "+active: bool"],
        ["+aabb_collides_with(rect)", "+update_collision(rect)", "+on_hit(car)", "+render(win)"],
        "#fff7ed",
    )
    uml_box(
        12.25, 6.55, 2.95, 1.58, "NitroPad",
        ["+position: tuple", "+charge: float", "+cooldown: int"],
        ["+aabb_collides_with(rect)", "+on_hit(car)", "+update()", "+render(win)"],
        "#ecfeff",
    )

    uml_box(
        0.75, 3.55, 3.15, 1.8, "StatsLogger",
        ["+file_path: str", "+data_buffer: dict", "+SAMPLE_INTERVAL: float"],
        ["+telemetry_bundle(...)", "+log_race_summary(summary)", "+log_competitor_results(rows)", "+export_to_csv()"],
        "#fdf2f8",
    )
    uml_box(
        4.45, 3.75, 2.75, 1.58, "Leaderboard",
        ["+file_path: str", "+entries: list", "+MAX_ENTRIES: int"],
        ["+submit(name, lap_time)", "+top(n)", "+_save()", "+_load()"],
        "#fef2f2",
    )
    uml_box(
        0.75, 1.38, 3.15, 1.58, "SectorTimer",
        ["+checkpoints: set", "+lap_start: float"],
        ["+on_race_start(time_s)", "+on_new_lap(time_s)", "+tick(player, checkpoints, ...)"],
        "#f0fdf4",
    )

    uml_box(
        8.8, 3.75, 3.05, 1.58, "EmbeddedTelemetryViewer",
        ["+stats_dir: str", "+out_dir: str", "+zoom: float", "+scroll_y: int"],
        ["+handle_event(event)", "+draw(surface)", "+_switch_race(delta)", "+_reload_image()"],
        "#f3e8ff",
    )
    uml_box(
        12.45, 3.75, 2.95, 1.58, "Telemetry report",
        ["+stats/*.csv", "+reports/*.png", "+pandas DataFrame"],
        ["+generate_report()", "+_build_race_payload()", "+_render_dashboard()"],
        "#f8fafc",
    )
    uml_box(
        8.8, 1.38, 3.05, 1.58, "Standings helpers",
        ["+player progress", "+AI progress", "+finish_time"],
        ["+compute_standings()", "+player_progress_score()"],
        "#f1f5f9",
    )
    module_box(
        6.05,
        5.78,
        2.25,
        0.58,
        "<<module>> main.py",
        "game loop / composition root",
    )

    # Inheritance and core simulation links
    arrow(2.08, 8.75, 2.08, 8.3, "inherits", hollow=True)
    elbow([(6.05, 6.06), (2.08, 6.06), (2.08, 6.65)], "updates player", label_index=0)
    elbow([(6.92, 6.36), (6.92, 6.55)])
    elbow([(7.75, 6.36), (7.75, 8.95), (7.4, 8.95)], "race state", label_index=0)
    elbow([(8.3, 6.08), (10.2, 6.08), (10.2, 8.72)], "track mask", label_index=1)
    elbow([(7.4, 7.35), (8.18, 7.35), (8.18, 9.18), (8.8, 9.18)], "PATH + mask", label_index=1)
    elbow([(3.4, 8.05), (3.72, 8.05), (3.72, 10.62), (10.18, 10.62), (10.18, 10.4)], "collision checks", label_index=2)

    # World object ownership and effects
    elbow([(11.65, 9.45), (12.25, 9.45)], "contains")
    elbow([(8.3, 5.98), (15.45, 5.98), (15.45, 9.45), (15.2, 9.45)], "obstacles", label_index=0)
    elbow([(8.3, 5.82), (15.45, 5.82), (15.45, 7.34), (15.2, 7.34)], "nitro pads", label_index=0)

    # Data and reporting links
    elbow([(4.35, 9.15), (4.06, 9.15), (4.06, 5.25), (3.9, 5.25)], "race summary", label_index=1)
    elbow([(3.9, 4.45), (4.45, 4.45)], "best laps")
    elbow([(2.35, 2.96), (2.35, 3.55)], "sector splits")
    elbow([(3.9, 3.75), (4.08, 3.75), (4.08, 1.16), (13.92, 1.16), (13.92, 3.75)], "exports CSV", dashed=True, label_index=3)
    elbow([(12.45, 4.48), (11.85, 4.48)], "loads PNG")
    elbow([(8.3, 5.78), (12.1, 5.78), (12.1, 1.95), (11.85, 1.95)], "standings input", dashed=True, label_index=1)

    ax.text(
        0.55,
        0.38,
        "Note: the main pygame loop composes these objects rather than being a class. "
        "Utility modules (world.py, hud.py, screen_menu.py, screen_results.py, telemetry_extra.py) "
        "call into these classes for rendering, collision, ranking, and telemetry.",
        fontsize=8,
        color="#475569",
    )

    plt.tight_layout()
    fig.savefig(path, format="pdf")
    plt.close(fig)


def build_uml_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    page_w, page_h = 22.0, 14.0

    def page(title, subtitle):
        fig, ax = plt.subplots(figsize=(19.5, 12.4))
        ax.set_xlim(0, page_w)
        ax.set_ylim(0, page_h)
        ax.axis("off")
        fig.subplots_adjust(left=0.02, right=0.985, bottom=0.035, top=0.91)
        ax.text(page_w / 2, 13.55, title, ha="center", va="center",
                fontsize=21, fontweight="bold")
        ax.text(page_w / 2, 13.18, subtitle, ha="center", va="center",
                fontsize=9.5, color="#64748b")
        return fig, ax

    def section(ax, x, y, w, h, title, color="#f8fafc"):
        ax.add_patch(FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.045", linewidth=1,
            edgecolor="#cbd5e1", facecolor=color, zorder=-3))
        ax.text(x + 0.18, y + h - 0.34, title, fontsize=9.2,
                fontweight="bold", color="#475569", zorder=4)

    def uml_box(ax, x, y, w, h, title, attrs, methods, color,
                module="", stereotype="class", attr_font=6.0, method_font=5.9):
        ax.add_patch(FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.025", linewidth=1.15,
            edgecolor="#1f2937", facecolor=color, zorder=1))
        title_h = 0.58 if module else 0.46
        attr_h = max(0.30, h * 0.36)
        ax.plot([x, x + w], [y + h - title_h, y + h - title_h],
                color="#1f2937", linewidth=0.9, zorder=2)
        ax.plot([x, x + w], [y + h - title_h - attr_h,
                             y + h - title_h - attr_h],
                color="#1f2937", linewidth=0.8, zorder=2)
        ax.text(x + 0.12, y + h - 0.14, f"<<{stereotype}>>",
                ha="left", va="top", fontsize=5.6, color="#64748b",
                family="monospace", zorder=3)
        ax.text(x + w / 2, y + h - (0.26 if module else 0.23), title,
                ha="center", va="center", fontsize=8.6, fontweight="bold",
                family="monospace", zorder=3)
        if module:
            ax.text(x + w / 2, y + h - 0.45, module,
                    ha="center", va="center", fontsize=5.8,
                    color="#475569", family="monospace", zorder=3)
        ax.text(x + 0.12, y + h - title_h - 0.14, "\n".join(attrs),
                ha="left", va="top", fontsize=attr_font, family="monospace",
                linespacing=1.13, zorder=3)
        ax.text(x + 0.12, y + h - title_h - attr_h - 0.14,
                "\n".join(methods), ha="left", va="top",
                fontsize=method_font, family="monospace",
                linespacing=1.13, zorder=3)

    def module_box(ax, x, y, w, h, title, lines, color="#ffffff",
                   stereotype="module", fontsize=6.0):
        ax.add_patch(FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.04", linewidth=1.05,
            edgecolor="#334155", facecolor=color, zorder=1))
        ax.text(x + 0.12, y + h - 0.14, f"<<{stereotype}>>",
                ha="left", va="top", fontsize=5.5, color="#64748b",
                family="monospace", zorder=3)
        ax.text(x + w / 2, y + h - 0.29, title,
                ha="center", va="center", fontsize=8.0,
                fontweight="bold", family="monospace", color="#111827",
                zorder=3)
        ax.text(x + 0.15, y + h - 0.60, "\n".join(lines),
                ha="left", va="top", fontsize=fontsize,
                family="monospace", color="#334155", linespacing=1.14,
                zorder=3)

    def data_box(ax, x, y, w, h, title, fields, color="#f8fafc"):
        module_box(ax, x, y, w, h, title, fields, color, "csv", 6.0)

    def edge(ax, pts, label="", dashed=False, hollow=False, label_index=None,
             color="#334155", lw=1.05, arrow=True, label_offset=0.1):
        xs, ys = zip(*pts)
        ax.plot(xs, ys, color=color, linewidth=lw,
                linestyle="--" if dashed else "-", solid_capstyle="round",
                zorder=0)
        if arrow:
            arrowstyle = "-|>"
            patch = FancyArrowPatch(
                pts[-2], pts[-1], arrowstyle=arrowstyle,
                mutation_scale=12 if hollow else 10, linewidth=lw, color=color,
                linestyle="--" if dashed else "-", shrinkA=0, shrinkB=4,
                zorder=0.5)
            if hollow:
                patch.set_facecolor("white")
            ax.add_patch(patch)
        if label:
            idx = label_index if label_index is not None else max(0, len(pts) // 2 - 1)
            idx = max(0, min(idx, len(pts) - 2))
            x1, y1 = pts[idx]
            x2, y2 = pts[idx + 1]
            ax.text((x1 + x2) / 2, (y1 + y2) / 2 + label_offset,
                    label, ha="center", va="center", fontsize=6.45,
                    color=color,
                    bbox=dict(facecolor="white", edgecolor="none",
                              pad=1.5, alpha=0.95),
                    zorder=4)

    def note(ax, x, y, w, h, title, body):
        ax.add_patch(FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.04", linewidth=0.9,
            edgecolor="#94a3b8", facecolor="#fffdf4", zorder=1))
        ax.text(x + 0.15, y + h - 0.17, title, ha="left", va="top",
                fontsize=7.4, fontweight="bold", color="#475569", zorder=3)
        ax.text(x + 0.15, y + h - 0.47, body, ha="left", va="top",
                fontsize=6.35, color="#475569", linespacing=1.18, zorder=3)

    def legend(ax, x, y):
        ax.text(x, y + 0.66, "Legend", fontsize=7.7,
                fontweight="bold", color="#475569")
        edge(ax, [(x, y + 0.43), (x + 1.05, y + 0.43)], "uses")
        edge(ax, [(x, y + 0.13), (x + 1.05, y + 0.13)], "reads/writes",
             dashed=True)
        edge(ax, [(x + 2.35, y + 0.43), (x + 3.4, y + 0.43)], "inherits",
             hollow=True)
        ax.text(x + 2.35, y + 0.02,
                "Notes clarify module-level ownership around class objects.",
                fontsize=6.25, color="#64748b")

    with PdfPages(path) as pdf:
        fig, ax = page(
            "Formula 67 - Detailed UML class diagram",
            "Page 1: domain classes, persistent objects, and major runtime relationships",
        )
        section(ax, 0.35, 3.55, 5.05, 9.35, "Vehicle model", "#f0f9ff")
        section(ax, 5.75, 1.25, 5.05, 11.65, "Race control", "#fffbea")
        section(ax, 11.15, 4.85, 5.05, 8.05, "World objects", "#f7fee7")
        section(ax, 16.45, 0.95, 5.2, 11.95, "Telemetry and presentation", "#faf5ff")

        classes = [
            (0.7, 10.45, 4.25, 2.05, "Car", "car.py", "#e0f2fe",
             ["+IMG: Surface", "+START_POS: tuple", "+max_vel: float",
              "+vel: float", "+angle: float"],
             ["+rotate(left, right)", "+drive(forward, backward)",
              "+apply_friction()", "+check_collision(mask, x=0, y=0)",
              "+draw(win)", "+reset()"]),
            (0.7, 7.65, 4.25, 2.25, "PlayerCar", "car.py", "#dbeafe",
             ["+nitro_charge: float", "+nitro_active: bool",
              "+nitro_max: float", "+NITRO_MULTIPLIER: float",
              "+_last_safe_pos: tuple"],
             ["+add_nitro(seconds)", "+update_nitro(dt, requested)",
              "+bounce_off_wall(track)", "+reset()"]),
            (0.7, 4.05, 4.25, 2.95, "AIRacer", "ai_racer.py", "#ede9fe",
             ["+name: str", "+personal_path: list", "+current_point: int",
              "+lap_times: list", "+finish_time: float", "+driver_seed: int"],
             ["+update(total_laps)", "+progress_score()", "+best_lap_time()",
              "-_build_personal_path(offset)", "-_steer_towards_lookahead()",
              "-_recover_from_border()"]),
            (6.1, 10.25, 4.25, 2.25, "RaceManager", "race.py", "#fef9c3",
             ["+TOTAL_LAPS: int", "+current_lap: int", "+lap_times: list",
              "+player_finished: bool", "+collision_count: int",
              "+nitro_burst_count: int"],
             ["+start_race()", "+track_lap_time()", "+end_race()",
              "+track_nitro_burst(active, speed)", "+register_collision()",
              "+race_summary()"]),
            (6.1, 7.35, 4.25, 2.25, "Track", "track.py", "#dcfce7",
             ["+surface: Surface", "+border_mask: Mask", "+finish_mask: Mask",
              "+boundary_points: list", "+checkpoints: list"],
             ["-_build_checkpoints(path)", "+get_track_path()",
              "+is_out_of_bounds(car)", "+at_finish_line(car)", "+draw(win)"]),
            (6.1, 4.55, 4.25, 2.05, "SectorTimer", "telemetry_extra.py", "#f0fdf4",
             ["-_next: int", "-_split_t0: float", "-_cool_until: float"],
             ["+on_race_start(time_s)", "+on_new_lap(time_s)",
              "+tick(player, checkpoints, lap, race_id, logger, time_s)"]),
            (11.55, 10.25, 4.25, 2.25, "Obstacle", "obstacle.py", "#ffedd5",
             ["+TYPES: dict", "+position: tuple", "+type: str",
              "+radius: int", "+speed_penalty: float", "+active: bool"],
             ["+rect: pygame.Rect", "+aabb_collides_with(car_rect)",
              "+update_collision(car_rect)", "+on_hit(car)",
              "-_build_sprite()", "+render(win)"]),
            (11.55, 7.35, 4.25, 2.25, "NitroPad", "obstacle.py", "#ccfbf1",
             ["+position: tuple", "+charge: float", "+radius: int",
              "+cooldown: int", "+cooldown_max: int"],
             ["+rect: pygame.Rect", "+aabb_collides_with(car_rect)",
              "+on_hit(car)", "+update()", "+render(win)",
              "+_get_sprites(radius)"]),
            (16.8, 9.15, 4.55, 3.35, "StatsLogger", "stats.py", "#fce7f3",
             ["+SAMPLE_INTERVAL: float", "+_FEATURE_FILES: dict",
              "+file_path: str", "+data_buffer: dict[str, list]",
              "+race_id: property", "-_last_sample_time: float"],
             ["+start_race()", "+telemetry_bundle(...)", "+log_sector_split(...)",
              "+log_collision_event(...)", "+log_nitro_event(...)",
              "+log_race_summary(summary)", "+log_competitor_results(rows)",
              "+export_to_csv(output_dir)"]),
            (16.8, 6.55, 4.55, 2.1, "Leaderboard", "stats.py", "#fee2e2",
             ["+MAX_ENTRIES: int", "+file_path: str", "+entries: list"],
             ["+submit(name, lap_time)", "+top(n=10)", "-_load()",
              "-_save()", "-_sort(entries)"]),
            (16.8, 3.55, 4.55, 2.35, "EmbeddedTelemetryViewer", "visualize.py", "#f3e8ff",
             ["+TOP_BAR: int", "+png_path: str", "+race_ids: list",
              "+current_race: int", "+scroll_x, scroll_y: int"],
             ["+handle_event(event)", "+draw(surface)", "-_switch_race(delta)",
              "-_reload_image()", "-_clamp_scroll(w, h)"]),
        ]
        overview = {
            "Car": (
                ["+position / velocity / angle", "+sprite + rotated mask cache"],
                ["+drive() / +apply_friction()", "+check_collision(mask)", "+draw() / +reset()"],
            ),
            "PlayerCar": (
                ["+nitro_charge / nitro_active", "+last safe track position"],
                ["+update_nitro()", "+bounce_off_wall(track)", "+add_nitro()"],
            ),
            "AIRacer": (
                ["+personal racing line", "+lap / finish state", "+border safety settings"],
                ["+update(total_laps)", "+progress_score()", "+best_lap_time()"],
            ),
            "RaceManager": (
                ["+current lap / race timer", "+lap times / finish state", "+race metrics counters"],
                ["+start_race()", "+track_lap_time()", "+race_summary()"],
            ),
            "Track": (
                ["+border mask / finish mask", "+checkpoints / path"],
                ["+is_out_of_bounds(car)", "+at_finish_line(car)", "+draw(win)"],
            ),
            "SectorTimer": (
                ["+next checkpoint", "+split timer cooldown"],
                ["+on_race_start()", "+on_new_lap()", "+tick(... logger ...)"],
            ),
            "Obstacle": (
                ["+type / radius / penalty", "+active collision state"],
                ["+update_collision(rect)", "+on_hit(car)", "+render(win)"],
            ),
            "NitroPad": (
                ["+charge / cooldown", "+pickup radius"],
                ["+aabb_collides_with(rect)", "+on_hit(car)", "+update() / +render()"],
            ),
            "StatsLogger": (
                ["+race_id", "+data_buffer", "+feature -> csv mapping"],
                ["+telemetry_bundle()", "+log_race_summary()", "+export_to_csv()"],
            ),
            "Leaderboard": (
                ["+top lap entries", "+MAX_ENTRIES"],
                ["+submit()", "+top()", "-_load() / -_save()"],
            ),
            "EmbeddedTelemetryViewer": (
                ["+png_path / race ids", "+scroll state"],
                ["+handle_event()", "+draw()", "-_switch_race()"],
            ),
        }
        for x, y, w, h, title, module, color, attrs, methods in classes:
            attrs, methods = overview.get(title, (attrs, methods))
            uml_box(
                ax, x, y, w, h, title, attrs, methods, color, module,
                attr_font=6.45, method_font=6.35,
            )

        module_box(ax, 6.1, 1.75, 4.25, 2.05, "standings.py",
                   ["+player_progress_score(player, race, path)",
                    "+compute_standings(player, ai, race, path)",
                    "returns sorted dict rows with rank/best_lap"],
                   "#f8fafc", "helper", 5.95)
        module_box(ax, 11.55, 5.15, 4.25, 1.35, "spawn_obstacles()",
                   ["factory function", "path -> randomized Obstacle list",
                    "cone/barrel/oil profiles"],
                   "#fff7ed", "factory", 6.05)
        module_box(ax, 16.8, 1.15, 4.55, 1.75, "visualize.py report",
                   ["+generate_report(stats_dir, race_id)",
                    "-_build_race_payload(...)", "-_render_dashboard(payload, race)",
                    "outputs reports/*.png"],
                   "#f8fafc", "report builder", 5.95)

        edge(ax, [(2.82, 7.65), (2.82, 10.45)], hollow=True)
        edge(ax, [(4.95, 8.85), (5.5, 8.85), (5.5, 8.45), (6.1, 8.45)],
             label_index=1)
        edge(ax, [(4.95, 5.75), (5.45, 5.75), (5.45, 7.95), (6.1, 7.95)],
             label_index=1)
        edge(ax, [(6.1, 8.9), (5.35, 8.9), (5.35, 11.45), (4.95, 11.45)],
             label_index=1)
        edge(ax, [(10.35, 8.8), (11.05, 8.8), (11.05, 11.35), (11.55, 11.35)],
             label_index=1)
        edge(ax, [(10.35, 8.25), (11.05, 8.25), (11.05, 8.45), (11.55, 8.45)],
             label_index=1)
        edge(ax, [(11.55, 5.82), (10.9, 5.82), (10.9, 10.9), (11.55, 10.9)],
             dashed=True, label_index=1)
        edge(ax, [(10.35, 11.35), (10.85, 11.35), (10.85, 12.85),
                  (19.08, 12.85), (19.08, 12.5)],
             label_index=2)
        edge(ax, [(10.35, 5.55), (15.95, 5.55), (15.95, 10.15), (16.8, 10.15)],
             dashed=True, label_index=1)
        edge(ax, [(16.8, 10.82), (15.95, 10.82), (15.95, 6.05), (10.35, 6.05)],
             dashed=True, label_index=1)
        edge(ax, [(19.08, 9.15), (19.08, 8.65)])
        edge(ax, [(21.35, 10.55), (21.72, 10.55), (21.72, 2.05), (21.35, 2.05)],
             dashed=True, label_index=1)
        edge(ax, [(19.08, 2.9), (19.08, 3.55)])
        edge(ax, [(4.95, 4.95), (5.55, 4.95), (5.55, 2.78), (6.1, 2.78)],
             dashed=True, label_index=1)
        edge(ax, [(4.95, 8.05), (5.25, 8.05), (5.25, 2.36), (6.1, 2.36)],
             dashed=True, label_index=1)
        edge(ax, [(8.22, 10.25), (8.22, 3.8)], "lap / finish status",
             dashed=True, label_index=0)

        note(ax, 0.65, 1.1, 4.9, 1.95, "Implementation note",
             "The game is not built as one giant class. main.py owns the loop\n"
             "and composes these classes, while world.py, hud.py, and screen\n"
             "modules act as controllers/renderers around the class model.")
        legend(ax, 11.55, 1.45)
        pdf.savefig(fig)
        plt.close(fig)

        fig, ax = page(
            "Formula 67 - Vehicle and race class detail",
            "Page 2: expanded class members with larger boxes and no text stacking",
        )
        section(ax, 0.35, 7.0, 10.45, 5.9, "Vehicle hierarchy", "#f0f9ff")
        section(ax, 11.15, 7.0, 10.5, 5.9, "Race timing and track state", "#fffbea")
        section(ax, 0.35, 0.95, 21.3, 5.45, "Progress, sector, and ranking helpers", "#f8fafc")

        detail_positions = {
            "Car": (0.8, 10.0, 4.75, 2.25),
            "PlayerCar": (0.8, 7.45, 4.75, 2.15),
            "AIRacer": (5.9, 7.45, 4.45, 4.8),
            "RaceManager": (11.65, 9.75, 4.75, 2.5),
            "Track": (16.7, 9.75, 4.45, 2.5),
            "SectorTimer": (11.65, 6.95, 4.75, 2.15),
        }
        detail_by_name = {item[4]: item for item in classes}
        for name, pos in detail_positions.items():
            _, _, _, _, title, module, color, attrs, methods = detail_by_name[name]
            uml_box(
                ax, *pos, title, attrs, methods, color, module,
                attr_font=6.35, method_font=6.15,
            )

        module_box(
            ax, 16.7, 6.95, 4.45, 2.15, "standings.py",
            ["+player_progress_score(player, race, path)",
             "+compute_standings(player, ai, race, path)",
             "sort by finish time, then progress"],
            "#f8fafc", "helper", 6.2,
        )
        module_box(
            ax, 0.8, 3.85, 6.0, 1.95, "race_intro.py",
            ["build_ai_racers(difficulty)", "reads DIFFICULTIES + PATH",
             "creates AIRacer instances with separate racing lines"],
            "#fef9c3", "factory", 6.25,
        )
        module_box(
            ax, 7.65, 3.85, 6.0, 1.95, "world.py",
            ["handle_input()", "handle_track_collision()",
             "handle_obstacles_and_nitro()", "draw_world()"],
            "#dbeafe", "controller", 6.25,
        )
        module_box(
            ax, 14.5, 3.85, 6.0, 1.95, "settings.py / assets.py",
            ["PATH, FPS, difficulty presets", "sprites, masks, window metrics",
             "track_to_screen() maps track space to display space"],
            "#f1f5f9", "support", 6.2,
        )

        edge(ax, [(3.18, 9.6), (3.18, 10.0)], "inherits", hollow=True)
        edge(ax, [(5.55, 8.55), (5.9, 8.55)], "player input")
        edge(ax, [(10.35, 9.05), (11.65, 8.05)], "sector/lap callbacks", dashed=True)
        edge(ax, [(10.35, 10.2), (11.65, 10.85)], "race state", dashed=True)
        edge(ax, [(10.35, 9.55), (16.7, 10.95)], "PATH + mask", dashed=True, label_index=0)
        edge(ax, [(16.4, 8.05), (16.7, 8.05)], "ranking rows", dashed=True)
        edge(ax, [(3.8, 3.85), (3.8, 7.45)], "constructs AI", dashed=True)
        edge(ax, [(10.65, 5.8), (10.65, 7.45)], "updates objects", dashed=True)
        edge(ax, [(17.5, 5.8), (17.5, 9.75)], "provides masks/path", dashed=True)
        legend(ax, 0.8, 1.35)
        pdf.savefig(fig)
        plt.close(fig)

        fig, ax = page(
            "Formula 67 - World and telemetry class detail",
            "Page 3: hazards, pickups, persistence, leaderboard, and report viewer",
        )
        section(ax, 0.35, 7.0, 10.45, 5.9, "Track objects", "#f7fee7")
        section(ax, 11.15, 7.0, 10.5, 5.9, "Telemetry classes", "#faf5ff")
        section(ax, 0.35, 0.95, 21.3, 5.45, "Persistent files and visual report", "#f8fafc")

        world_positions = {
            "Obstacle": (0.8, 9.65, 4.75, 2.6),
            "NitroPad": (5.95, 9.65, 4.4, 2.6),
            "StatsLogger": (11.65, 8.65, 4.95, 3.6),
            "Leaderboard": (16.95, 10.0, 4.25, 2.25),
            "EmbeddedTelemetryViewer": (16.95, 7.35, 4.25, 2.25),
        }
        for name, pos in world_positions.items():
            _, _, _, _, title, module, color, attrs, methods = detail_by_name[name]
            uml_box(
                ax, *pos, title, attrs, methods, color, module,
                attr_font=6.15, method_font=5.95,
            )

        module_box(
            ax, 0.8, 4.45, 4.75, 1.65, "spawn_obstacles()",
            ["factory function", "randomizes cone / barrel / oil",
             "uses path nodes as spawn candidates"],
            "#fff7ed", "factory", 6.15,
        )
        module_box(
            ax, 5.95, 4.45, 4.4, 1.65, "world.py collision loop",
            ["obstacle hit -> register collision",
             "nitro pad hit -> add_nitro()",
             "track hit -> wall collision event"],
            "#dbeafe", "controller", 6.05,
        )
        data_box(
            ax, 11.65, 4.25, 4.95, 1.95, "stats/*.csv",
            ["speed / position / input_sample", "gap_sample / sector_split",
             "lap_time / race_summary / competitor", "event stream csv files"],
            "#fff7ed",
        )
        module_box(
            ax, 16.95, 4.45, 4.25, 1.65, "visualize.py report",
            ["generate_report()", "_build_race_payload()",
             "_render_dashboard() -> reports/*.png"],
            "#f3e8ff", "report builder", 6.05,
        )
        data_box(
            ax, 16.95, 2.0, 4.25, 1.55, "reports/*.png",
            ["dashboard image", "loaded by EmbeddedTelemetryViewer",
             "scrollable in the game"],
            "#f8fafc",
        )

        edge(ax, [(5.55, 10.95), (5.95, 10.95)], "same rect-hit API")
        edge(ax, [(3.2, 6.1), (3.2, 9.65)], "creates", dashed=True)
        edge(ax, [(7.95, 6.1), (7.95, 9.65)], "calls on_hit()", dashed=True)
        edge(ax, [(10.35, 5.35), (11.65, 10.1)], "logs events", dashed=True, label_index=0)
        edge(ax, [(14.12, 8.65), (14.12, 6.2)], "export_to_csv()", dashed=True)
        edge(ax, [(16.6, 5.2), (16.95, 5.2)], "read csv", dashed=True)
        edge(ax, [(19.08, 4.45), (19.08, 3.55)], "render PNG", dashed=True)
        edge(ax, [(19.08, 3.55), (19.08, 7.35)], "load image")
        edge(ax, [(16.95, 10.95), (16.6, 10.95), (16.6, 9.9)],
             "best lap rows", dashed=True)
        legend(ax, 0.8, 1.35)
        pdf.savefig(fig)
        plt.close(fig)

        fig, ax = page(
            "Formula 67 - Runtime module dependency map",
            "Page 4: controller, rendering, AI, and telemetry flow around the class model",
        )
        section(ax, 0.35, 9.3, 21.3, 3.5, "Configuration and assets")
        section(ax, 0.35, 4.5, 21.3, 4.35, "Runtime controllers and rendering", "#f0f9ff")
        section(ax, 0.35, 0.95, 21.3, 3.1, "Telemetry data pipeline", "#faf5ff")

        modules = [
            (9.1, 6.55, 3.8, 1.7, "main.py",
             ["composition root", "MENU -> COUNTDOWN -> RACING",
              "RESULTS -> TELEMETRY", "owns clock, objects, state"], "#ffffff", "module"),
            (0.8, 10.3, 4.2, 1.75, "settings.py",
             ["FPS / MENU_FPS", "DIFFICULTIES", "PATH / NITRO_PAD_POSITIONS",
              "COUNTDOWN_SECONDS"], "#f1f5f9", "config"),
            (5.8, 10.3, 4.2, 1.75, "assets.py",
             ["pygame surfaces", "TRACK_BORDER_MASK", "PLAYFIELD_RECT",
              "track_to_screen(x, y)"], "#f1f5f9", "asset loader"),
            (10.8, 10.3, 4.2, 1.75, "race_intro.py",
             ["build_ai_racers(difficulty)", "draw_countdown_overlay(win, elapsed)",
              "driver profiles + grid slots"], "#fef9c3", "factory/controller"),
            (16.0, 10.3, 4.8, 1.75, "domain classes",
             ["Car / PlayerCar / AIRacer", "RaceManager / Track",
              "Obstacle / NitroPad"], "#ecfeff", "class layer"),
            (1.0, 6.55, 4.25, 1.8, "screen_menu.py",
             ["draw_start_screen(...)", "draw_waiting_overlay(...)",
              "difficulty picker", "leaderboard panel"], "#fef2f2", "view"),
            (1.0, 4.95, 4.25, 1.15, "screen_results.py",
             ["draw_results_screen(...)", "podium, stats tiles, retry/menu"],
             "#fef2f2", "view"),
            (6.0, 5.05, 3.95, 2.6, "world.py",
             ["draw_world(...)", "handle_input(...)",
              "handle_obstacles_and_nitro(...)", "handle_track_collision(...)"],
             "#dbeafe", "controller"),
            (13.95, 6.75, 3.25, 1.45, "hud.py",
             ["draw_hud()", "draw_minimap()", "draw_speedometer()",
              "draw_standings_panel()"], "#e0f2fe", "view"),
            (17.85, 6.75, 3.25, 1.45, "scenery.py",
             ["draw_spectator_scenery()", "grandstands / sponsor boards",
              "east crowd strip"], "#dcfce7", "view"),
            (13.95, 4.95, 3.25, 1.35, "standings.py",
             ["player_progress_score()", "compute_standings()", "rank rows"],
             "#f8fafc", "helper"),
            (17.85, 4.95, 3.25, 1.35, "telemetry_extra.py",
             ["nearest_path_index()", "SectorTimer", "gap_progress_units()"],
             "#f0fdf4", "helper"),
            (1.0, 1.55, 4.15, 1.65, "stats.py",
             ["StatsLogger", "Leaderboard", "CSV append/merge/export"],
             "#fce7f3", "persistence"),
            (11.0, 1.45, 4.2, 1.8, "visualize.py",
             ["generate_report()", "EmbeddedTelemetryViewer",
              "pandas + matplotlib dashboard"], "#f3e8ff", "analytics/view"),
        ]
        for x, y, w, h, title, lines, color, stereo in modules:
            module_box(ax, x, y, w, h, title, lines, color, stereo, 5.9)
        data_box(ax, 6.0, 1.35, 4.05, 2.0, "stats/*.csv",
                 ["speed, position, input_sample", "gap_sample, sector_split",
                  "lap_time, race_summary", "collision/nitro/steering events"],
                 "#fff7ed")
        data_box(ax, 16.2, 1.55, 4.5, 1.65, "reports/*.png",
                 ["telemetry dashboard image", "loaded inside pygame viewer",
                  "also viewable standalone"], "#f8fafc")

        edge(ax, [(5.0, 11.15), (5.8, 11.15)], "PATH scale")
        edge(ax, [(10.0, 11.15), (10.8, 11.15)], "sprites/masks")
        edge(ax, [(15.0, 11.15), (16.0, 11.15)], "constructs")
        edge(ax, [(11.0, 10.3), (11.0, 8.25)], "build AI + countdown")
        edge(ax, [(9.1, 7.35), (5.25, 7.35)], "menu state")
        edge(ax, [(9.1, 6.95), (5.25, 5.5)], "results state")
        edge(ax, [(10.0, 6.55), (9.4, 5.05)], "update loop", label_index=0)
        edge(ax, [(12.9, 7.3), (13.95, 7.3)], "HUD overlay")
        edge(ax, [(12.9, 6.9), (17.85, 7.15)], "spectators")
        edge(ax, [(9.95, 5.6), (13.95, 5.62)], "standing rows")
        edge(ax, [(9.95, 5.32), (17.85, 5.62)], "sector/gap helpers")
        edge(ax, [(10.95, 6.55), (16.0, 10.3)], "mutates classes",
             dashed=True, label_index=0)
        edge(ax, [(9.1, 6.55), (3.08, 3.2)], "race summary / events",
             dashed=True, label_index=0)
        edge(ax, [(5.15, 2.35), (6.0, 2.35)], "export_to_csv()", dashed=True)
        edge(ax, [(10.05, 2.35), (11.0, 2.35)], "read_csv_df()", dashed=True)
        edge(ax, [(15.2, 2.35), (16.2, 2.35)], "render PNG", dashed=True)
        edge(ax, [(13.1, 3.25), (13.1, 6.55), (12.9, 6.55)],
             "viewer mode", dashed=True, label_index=0)
        note(ax, 0.8, 12.35, 6.15, 0.75, "Why this page exists",
             "Several important relationships are module-level functions, not classes.\n"
             "This page shows how those controllers wire the class diagram together.")
        legend(ax, 15.6, 12.25)
        pdf.savefig(fig)
        plt.close(fig)

        fig, ax = page(
            "Formula 67 - Telemetry class and data detail",
            "Page 5: CSV feature groups, report builder, viewer interaction, and leaderboard persistence",
        )
        section(ax, 0.35, 7.15, 21.3, 5.75, "Telemetry producers", "#fff7ed")
        section(ax, 0.35, 3.7, 21.3, 2.95, "CSV persistence layer")
        section(ax, 0.35, 0.9, 21.3, 2.35, "Analysis and presentation", "#faf5ff")
        producer_boxes = [
            (0.8, 9.25, 4.65, 2.85, "RaceManager", "race.py", "#fef9c3",
             ["+lap_times", "+collision_count", "+nitro_duration",
              "+steering_left/right", "+max_speed"],
             ["+track_lap_time()", "+track_nitro_burst()", "+race_summary()"]),
            (6.0, 9.25, 4.65, 2.85, "StatsLogger", "stats.py", "#fce7f3",
             ["+data_buffer", "+_FEATURE_FILES", "+race_id",
              "+SAMPLE_INTERVAL"],
             ["+telemetry_bundle()", "+log_feature()", "+log_race_summary()",
              "+log_competitor_results()", "+export_to_csv()"]),
            (11.2, 9.25, 4.65, 2.85, "SectorTimer", "telemetry_extra.py", "#f0fdf4",
             ["-_next", "-_split_t0", "-_cool_until"],
             ["+on_race_start()", "+on_new_lap()",
              "+tick(..., stats_logger, time_s)"]),
        ]
        for x, y, w, h, title, module, color, attrs, methods in producer_boxes:
            uml_box(ax, x, y, w, h, title, attrs, methods, color, module)
        module_box(ax, 16.4, 9.25, 4.65, 2.85, "world.py logging points",
                   ["handle_input -> steering/cornering",
                    "handle_obstacles_and_nitro -> collision/nitro",
                    "handle_track_collision -> wall/lap finish",
                    "main loop -> speed/position/gap samples"],
                   "#dbeafe", "controller", 5.75)

        data_box(ax, 0.8, 4.25, 3.55, 1.75, "motion series",
                 ["speed.csv", "position.csv", "input_sample.csv", "gap_sample.csv"],
                 "#eef2ff")
        data_box(ax, 4.85, 4.25, 3.55, 1.75, "race summary",
                 ["lap_time.csv", "race_summary.csv", "competitor.csv",
                  "leaderboard.csv"], "#fef2f2")
        data_box(ax, 8.9, 4.25, 3.55, 1.75, "event streams",
                 ["steering_event.csv", "collision_event.csv", "nitro_event.csv",
                  "cornering_event.csv"], "#fff7ed")
        data_box(ax, 12.95, 4.25, 3.55, 1.75, "sector detail",
                 ["sector_split.csv", "race_id", "lap_number",
                  "sector_index", "split_s"], "#f0fdf4")
        uml_box(ax, 17.0, 4.25, 3.95, 1.75, "Leaderboard",
                ["+entries: list", "+MAX_ENTRIES: 10"],
                ["+submit()", "+top()", "-_sort()", "-_save()"],
                "#fee2e2", "stats.py", attr_font=5.95, method_font=5.75)
        module_box(ax, 1.0, 1.35, 4.9, 1.45, "generate_report()",
                   ["reads selected race id", "builds KPI/chart payload",
                    "renders dashboard PNG"], "#f3e8ff", "visualize.py", 5.95)
        module_box(ax, 8.35, 1.35, 4.9, 1.45, "EmbeddedTelemetryViewer",
                   ["pan/scroll race dashboard", "prev/next race",
                    "return to menu/results"], "#ede9fe", "view class", 5.95)
        data_box(ax, 15.7, 1.35, 4.9, 1.45, "reports/*.png",
                 ["single rendered telemetry dashboard", "loaded by pygame.image.load()",
                  "shown in TELEMETRY state"], "#f8fafc")

        edge(ax, [(5.45, 10.7), (6.0, 10.7)], "summary rows")
        edge(ax, [(10.65, 10.65), (11.2, 10.65)], "sector calls", dashed=True)
        edge(ax, [(16.4, 10.65), (10.65, 10.65)], "runtime events",
             dashed=True, label_index=0)
        edge(ax, [(8.35, 9.25), (2.58, 6.0)], "sample buffers",
             dashed=True, label_index=0)
        edge(ax, [(8.35, 9.25), (6.62, 6.0)], "lap/best data",
             dashed=True, label_index=0)
        edge(ax, [(8.35, 9.25), (10.68, 6.0)], "event rows",
             dashed=True, label_index=0)
        edge(ax, [(12.65, 9.25), (14.72, 6.0)], "split rows",
             dashed=True, label_index=0)
        edge(ax, [(8.35, 9.25), (18.98, 6.0)], "best lap submit",
             dashed=True, label_index=0)
        edge(ax, [(10.68, 4.25), (3.45, 2.8)], "pandas read",
             dashed=True, label_index=0)
        edge(ax, [(3.45, 1.35), (8.35, 2.08)], "render_fn(race_id)",
             dashed=True, label_index=0)
        edge(ax, [(13.25, 2.08), (15.7, 2.08)], "PNG path")
        edge(ax, [(15.7, 1.68), (13.25, 1.68)], "viewer loads", dashed=True)
        note(ax, 0.75, 12.25, 6.6, 0.68, "Detail level",
             "This page makes telemetry responsibilities explicit so the class diagram\n"
             "shows more than only object names.")
        legend(ax, 15.8, 12.15)
        pdf.savefig(fig)
        plt.close(fig)


def main() -> None:
    build_proposal_pdf(DOCS / "PROJECT_PROPOSAL.pdf")
    build_uml_pdf(DOCS / "UML_Class_Diagram.pdf")
    print(f"Wrote:\n  {(DOCS / 'PROJECT_PROPOSAL.pdf')}\n  {(DOCS / 'UML_Class_Diagram.pdf')}")


if __name__ == "__main__":
    main()
