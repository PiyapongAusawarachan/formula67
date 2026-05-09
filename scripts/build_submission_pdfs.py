#!/usr/bin/env python3
"""Spawns PDFs in ``docs/`` for the class hand-in (needs matplotlib)."""
from __future__ import annotations

from pathlib import Path

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


def build_uml_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(11, 8.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 7)
    ax.axis("off")
    ax.set_title(
        "Formula 67 — UML class diagram (high level)",
        fontsize=14,
        fontweight="bold",
        pad=12,
    )

    def box(x, y, w, h, text, fontsize=8):
        r = FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.03",
            linewidth=1.2,
            edgecolor="#222",
            facecolor="#f6f8ff",
        )
        ax.add_patch(r)
        ax.text(
            x + w / 2,
            y + h / 2,
            text,
            ha="center",
            va="center",
            fontsize=fontsize,
            family="monospace",
        )
        return (x + w / 2, y + h)

    def arrow(x1, y1, x2, y2, label=None):
        kw = dict(
            arrowstyle="-|>",
            mutation_scale=12,
            linewidth=1,
            color="#333",
            shrinkA=4,
            shrinkB=4,
        )
        a = FancyArrowPatch((x1, y1), (x2, y2), **kw)
        ax.add_patch(a)
        if label:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            ax.text(mx, my + 0.12, label, ha="center", fontsize=7, color="#555")

    box(1.0, 5.0, 2.2, 0.85, "Car\ncar.py\n+max_vel, vel, angle\n+drive()\n+check_collision()")
    box(1.0, 3.55, 2.2, 0.95, "PlayerCar\ncar.py\n+nitro_charge\n+nitro_active")
    arrow(2.1, 5.0, 2.1, 4.55, "inherits")

    box(4.0, 5.1, 2.2, 0.75, "Track\ntrack.py\n+border_mask, path\n+at_finish_line()")
    box(4.0, 3.9, 2.2, 0.75, "RaceManager\nrace.py\n+laps, lap_times\n+race_summary()")

    box(6.8, 5.1, 2.0, 0.75, "Obstacle\nobstacle.py\n+aabb hit")
    box(6.8, 3.95, 2.0, 0.65, "NitroPad\nobstacle.py\n+charge")

    box(0.6, 1.9, 2.4, 0.9, "StatsLogger\nstats.py\n+log_*, export_to_csv()")
    box(3.3, 1.9, 2.0, 0.9, "Leaderboard\nstats.py\n+top 10 laps")

    box(6.0, 1.9, 2.3, 0.9, "AIRacer\nai_racer.py\n+path follow")

    box(3.5, 0.35, 3.0, 0.75, "EmbeddedTelemetryViewer\nvisualize.py\n(optional embed)")

    arrow(3.2, 5.45, 4.0, 5.45)
    arrow(3.2, 4.8, 4.0, 4.35)
    arrow(5.1, 3.9, 5.1, 2.8, "updates")
    arrow(2.4, 3.55, 3.3, 2.55, "logs")
    arrow(5.5, 2.35, 6.0, 2.35, "sorts")
    arrow(7.8, 5.1, 3.2, 5.25, "collides")

    ax.text(
        0.5,
        0.08,
        "Relationships are simplified: main loop composes Track, cars, RaceManager, "
        "obstacles, StatsLogger, and AI. See source modules for full attributes/methods.",
        fontsize=8,
        color="#444",
    )

    plt.tight_layout()
    fig.savefig(path, format="pdf")
    plt.close(fig)


def main() -> None:
    build_proposal_pdf(DOCS / "PROJECT_PROPOSAL.pdf")
    build_uml_pdf(DOCS / "UML_Class_Diagram.pdf")
    print(f"Wrote:\n  {(DOCS / 'PROJECT_PROPOSAL.pdf')}\n  {(DOCS / 'UML_Class_Diagram.pdf')}")


if __name__ == "__main__":
    main()
