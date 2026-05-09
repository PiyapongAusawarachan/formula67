# Formula 67

## Project description

- **Project by:** Piyapong Ausawarachan  
- **Course:** Computer Programming II — Software and Knowledge Engineering, Kasetsart University  
- **Game genre:** Arcade, top-down racing  
- **What it is:** Python + pygame racer: three laps, AI grid, nitro, obstacles by difficulty. While you play, telemetry goes to `stats/*.csv`; `visualize.py` turns that into `reports/telemetry_report.png`. The long-form write-up (overview, UML, data section) is in [DESCRIPTION.md](DESCRIPTION.md).

---

## Installation

### Clone

```sh
git clone https://github.com/PiyapongAusawarachan/formula67.git
cd formula67
```

If the folder name differs, `cd` into wherever you cloned it.

### Virtual environment + dependencies

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

## Running guide

Activate `.venv` and stay in the **repository root**.

**Windows:**

```bat
python main.py
```

**macOS / Linux:**

```sh
python3 main.py
```

**Regenerate the telemetry PNG** (same data your submission screenshots should show):

```sh
python visualize.py
```

On Windows, if `python3` is missing, use `python` for all commands above.

---

## Tutorial / usage

1. **`main.py`** — start here.  
2. **Menu:** click a difficulty card, or press **1 / 2 / 3**, or **← →** / **A D**. **Space** starts the light sequence.  
3. **Driving:** **WASD** — **W/S** gas / brake, **A/D** steer (arrow keys do the same), **Shift** nitro when the bar has charge. Hit nitro pads on the track.  
4. Finish **3 laps** crossing the start/finish the right way (same as real circuits: you need sequence + direction the game expects).  
5. **Results** screen shows order and stats; CSVs on disk update for that race.  
6. **F11** fullscreen, **Esc** quit.

If `stats/` is thin, you can run `python seed_data.py` once (see that file’s docstring) to bulk-fill demo rows before recording your video.

---

## Game features

- Grass collision via **mask**; finish line also mask-based  
- Obstacles + nitro pads use **bounding boxes** vs the car rect  
- **3 difficulties** — obstacle count + AI parameters  
- **HUD:** lap, race time, collision count, position, nitro bar, minimap, speedometer  
- **Data:** live logging → **CSVs** → **matplotlib** dashboard PNG  
- **Leaderboard:** `leaderboard.csv` (best laps)

---

## Known bugs

- Fullscreen + multi-monitor / HiDPI can act weird on some setups; **F11** again or run windowed if needed.  
- If anything else breaks, note the OS + pygame version — I tested mainly on macOS and standard pygame installs.

---

## Unfinished work

- Fancy export formats (PDF report, extra pages) — not required; the course figure is the PNG from `visualize.py`.  
- **You must** paste your real **YouTube** link into [DESCRIPTION.md](DESCRIPTION.md) before the hard deadline. Gameplay and visualization screenshots are already under `screenshots/`.  
- GitHub **releases/tags** (`22_Apr_Version`, `10_May_Version`) and the class spreadsheet are on you — I can’t click “submit” for you.

---

## External sources

- **Libraries:** pygame, matplotlib, pandas — pinned loosely in [requirements.txt](requirements.txt).  
- **Art / credits:** [ATTRIBUTION.md](ATTRIBUTION.md)  
- **License:** [LICENSE](LICENSE) (MIT)

---

## Repo map

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
