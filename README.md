# Formula 67

**Computer Programming 2 — Software and Knowledge Engineering, Kasetsart University**

Arcade racing game with telemetry logging and post-race analysis (Python / pygame).

**All game source code lives in the [`formula/`](formula/) folder** (run install and `main.py` from there).

---

## 1. Project overview

This project is a **high-speed arcade racing game** where the player drives a car on a fixed track with optional obstacles. The focus is on **precision driving and speed management**, backed by a **telemetry pipeline** that records live gameplay and exports data for **performance visualization** after each race.

---

## 2. Project review

Typical 2D racing tutorials stop at movement and collision. This project extends that with a **telemetry system** that records granular data (e.g. speed samples, steering events, lap times, collisions, nitro usage) so you can produce **post-race analysis** comparable to a small professional telemetry report.

---

## 3. Programming development

### 3.1 Game concept

| Area | Description |
|------|-------------|
| **Mechanics** | Keyboard input to accelerate, brake, and steer through corners; mask-based track boundaries. |
| **Objectives** | Complete **three laps** in the shortest total time while avoiding obstacles that penalize progress. |
| **Key features** | Nitro boost pads, dynamic obstacle spawning (by difficulty), **real-time HUD** (lap, time, hits, position, nitro, minimap, speedometer). |

### 3.2 Object-oriented implementation

The codebase maps to the required class responsibilities as follows:

| Class | Role | Main module |
|--------|------|-------------|
| **Car** | Physics and movement (`drive`, `applyFriction`, mask `checkCollision`). | `formula/car.py` (`Car`, `PlayerCar`) |
| **Track** | Environment, boundaries, finish line, path / checkpoints. | `formula/track.py` (`Track`) |
| **RaceManager** | Game state and timing (`startRace`, `trackLapTime`, `resetGame`, lap totals). | `formula/race.py` (`RaceManager`) |
| **Obstacle / NitroPad** | Interactive elements (`onHit`, `render`, AABB where applicable). | `formula/obstacle.py` |
| **StatsLogger** | Data collection and CSV export (`logFeature`-style APIs, `export_to_csv`). | `formula/stats.py` (`StatsLogger`) |

Additional types: **AIRacer** (`formula/ai_racer.py`), **Leaderboard** (`formula/stats.py`), UI split across `formula/screen_menu.py`, `formula/screen_results.py`, `formula/hud.py`, `formula/world.py`.

### 3.3 Algorithms involved

- **Collision detection:** AABB for obstacles and nitro pads; **mask** collision for track borders and finish line.
- **Sorting:** Leaderboard keeps **top 10** lap times (insertion-style ordering in `Leaderboard`).
- **Event-driven flow:** Keyboard and finish-line events drive laps, stats sampling, and end-of-race export.

---

## 4. Statistical data (project stats)

### 4.1 Data features (≥ five features, ≥ 100 records each over repeated play)

| # | Feature | Purpose | Source (conceptual) | Typical visualization |
|---|---------|---------|------------------------|-------------------------|
| 1 | **Speed** (pixels / second) | Driving performance and consistency | Sampled from player velocity | Line chart (speed vs time), histogram |
| 2 | **Steering input** | Control behaviour, left vs right | `StatsLogger` steering events / counts | Table (count + %), pie chart |
| 3 | **Lap time** (seconds) | Performance and improvement | `RaceManager` lap timing | Table (mean, min, max, median, std dev) |
| 4 | **Collision count** (per race / events) | Mistakes and difficulty | Wall + obstacle events | Tables, relation analysis |
| 5 | **Nitro active duration** (seconds) | Nitro usage efficiency | Nitro bursts from player state | Scatter (e.g. nitro vs speed) |

Sampling is **automatic during gameplay**; accumulating **100+ rows per feature** is done across **multiple races** and/or `formula/seed_data.py` where used.

### 4.2 Data recording

- Data is collected **during gameplay** and written under **`formula/stats/`** as **CSV** files.
- After each finished race, logs are flushed/exported as configured in `StatsLogger` / `main.py`.

### 4.3 Analysis report (visualize)

The reporting pipeline (`formula/visualize.py`, output under `formula/reports/`) is aligned with the course expectations:

- **Tables:** e.g. speed summary, steering summary, lap-time statistics (mean, min, max, median, std dev).
- **Graphs (multiple types, no duplicate type required in one report):** e.g. **line** (speed vs time), **histogram** (speed distribution), **scatter** (nitro vs speed), **pie** (steering left/right share).

Exact charts depend on the current `visualize.py` implementation and available CSV columns.

---

## 5. Project planning timeline (from proposal)

| Week | Task |
|------|------|
| 8 | Proposal submission / project initiation |
| 9 | Core movement and OOP structure |
| 10 | Track design and collision detection |
| 11 | StatsLogger + CSV integration |
| 12 | Data collection (gameplay → 100+ records per feature) |
| 13 | Data visualization and analysis report |
| 14 | Submission week (draft) |

---

## 6. Document version (proposal PDF)

| Field | Value |
|--------|--------|
| **Version** | 4.0 |
| **Date** | 6 March 2025 |
| **Editor** | Piyapong Ausawarachan |

---

## Quick start

```bash
cd formula
pip install -r requirements.txt
python main.py
```

**Telemetry dashboard (matplotlib; writes PNG under `formula/reports/`, e.g. `telemetry_report.png`):**

```bash
cd formula
python visualize.py
```

---

## Repository layout

| Path | Description |
|------|-------------|
| [`formula/main.py`](formula/main.py) | Game loop and state machine |
| [`formula/settings.py`](formula/settings.py) | Difficulty presets, path geometry, timing |
| [`formula/assets.py`](formula/assets.py) | Display, fonts, sprites |
| [`formula/car.py`](formula/car.py) | Car / `PlayerCar` |
| [`formula/track.py`](formula/track.py), [`obstacle.py`](formula/obstacle.py), [`race.py`](formula/race.py) | Track, obstacles, race manager |
| [`formula/stats.py`](formula/stats.py) | `StatsLogger`, `Leaderboard`, CSV paths |
| [`formula/visualize.py`](formula/visualize.py) | Report generation |
| [`formula/stats/`](formula/stats/) | Runtime CSV telemetry |
| [`formula/reports/`](formula/reports/) | Generated charts (PNG) |

A copy of this documentation also exists at [`formula/README.md`](formula/README.md).

---

## Controls (in-game)

- **W / S** — accelerate / brake  
- **A / D** — steer  
- **Shift** — nitro (when charged)  
- **F11** — toggle fullscreen  
- **Esc** — quit  

Menu: choose difficulty (click, **1 / 2 / 3**, or **← / →** / **A / D**), **Space** to start.
