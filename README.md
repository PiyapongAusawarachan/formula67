# Formula 67

## Project Information

| Item | Detail |
|------|--------|
| Project | Formula 67 |
| Developer | Piyapong Ausawarachan |
| Course | Computer Programming II, Software and Knowledge Engineering, Kasetsart University |
| Genre | Top-down arcade racing |
| Technology | Python, pygame, pandas, matplotlib |

Formula 67 is a three-lap top-down racing game with AI opponents, nitro pads,
obstacles, difficulty settings, and a telemetry pipeline. During gameplay, race
data is written to `stats/*.csv`; `visualize.py` then converts those files into
the report image stored in `reports/telemetry_report.png`. The full project
description, UML reference, data explanation, and submission notes are provided
in [DESCRIPTION.md](DESCRIPTION.md).

---

## Installation

### Clone the Repository

```sh
git clone https://github.com/PiyapongAusawarachan/formula67.git
cd formula67
```

If the repository folder name is different, change into that folder before
running the next commands.

### Virtual Environment and Dependencies

**Windows (cmd / PowerShell):**

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**macOS / Linux:**

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Running Guide

Activate `.venv` and stay in the **repository root**.

**Windows:**

```bat
python main.py
```

**macOS / Linux:**

```sh
python3 main.py
```

**Regenerate the telemetry report image:**

```sh
python visualize.py
```

On Windows installations where `python3` is unavailable, use `python` for the
same commands.

---

## Usage

1. Run `main.py` from the repository root.
2. On the menu screen, select a difficulty card with the mouse, press `1`, `2`,
   or `3`, or use the arrow keys / `A` and `D`. Press `Space` to start the
   countdown sequence.
3. Drive with `WASD` or the arrow keys. Use `Shift` for nitro when charge is
   available.
4. Complete three valid laps by crossing the start/finish line in the expected
   direction.
5. Review the results screen. The race data is exported to CSV after the race.
6. Press `F11` to toggle fullscreen, or `Esc` to quit.

For demonstration data, run `python seed_data.py` once from the repository root.
This fills the telemetry folder with additional sample races for the
visualization report.

---

## Main Features

- Mask-based track border and finish-line collision
- Obstacles and nitro pads with bounding-box interaction
- Three difficulty modes with different AI and obstacle settings
- HUD with lap count, time, hits, position, nitro, minimap, and speedometer
- Telemetry logging from gameplay to CSV files
- Matplotlib report generation from recorded telemetry
- Persistent best-lap leaderboard in `leaderboard.csv`

---

## Known Issues

- Fullscreen behavior may vary on multi-monitor or HiDPI displays. If this
  occurs, press `F11` again or run the game in windowed mode.
- The project was tested primarily on macOS with a standard pygame
  installation.

---

## Final Submission Notes

- Paste the final YouTube presentation link into [DESCRIPTION.md](DESCRIPTION.md)
  before submission.
- Create the required GitHub releases or tags: `22_Apr_Version` and
  `10_May_Version`.
- Submit the repository link through the course submission form or spreadsheet.
- Gameplay and visualization screenshots are already organized under
  `screenshots/`.

---

## External Sources

- Libraries: pygame, matplotlib, pandas, and numpy; see
  [requirements.txt](requirements.txt).
- Art and asset references: [ATTRIBUTION.md](ATTRIBUTION.md).
- Project license: [LICENSE](LICENSE).

---

## Repository Structure

| Path | Role |
|------|------|
| `main.py` | Game loop |
| `car.py`, `track.py`, `race.py`, `obstacle.py`, `ai_racer.py` | Core simulation |
| `world.py`, `hud.py`, `screen_menu.py`, `screen_results.py`, `race_intro.py` | Drawing + UI |
| `stats.py` | Logging + leaderboard |
| `visualize.py` | Charts |
| `stats/` | CSV telemetry |
| `reports/` | Output PNG |
| `screenshots/` | Gameplay + visualization screenshots required for submission |
| `docs/` | Proposal, UML PDFs, and submission checklist |
| `DESCRIPTION.md` | Full project description for grading |
