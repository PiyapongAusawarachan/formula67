# Project Description — Formula 67

Formula 67 is a Python-based top-down racing game developed for **Computer
Programming II**, Software and Knowledge Engineering, Kasetsart University. The
project combines pygame gameplay, object-oriented game logic, CSV telemetry, and
matplotlib/pandas data visualization.

---

## 1. Project Overview

- **Project name:** Formula 67  

- **Brief description:** Formula 67 is a 2D racing game where the player
  completes three laps against AI-controlled cars. The game includes nitro pads,
  track obstacles, difficulty settings, a live HUD, a minimap, and a results
  screen. Race data is recorded automatically through `StatsLogger` in
  `stats.py`, which writes UTF-8 CSV files under `stats/`. The visualization
  module reads those files and generates `reports/telemetry_report.png`, a
  dashboard containing tables and multiple chart types.

- **Problem statement:** Racing games usually present only final results, such
  as lap time or finishing position. This project adds a telemetry layer so that
  driving behavior can be reviewed through recorded data, including speed,
  steering, collisions, nitro usage, sector splits, and race classification.

- **Target users:** This project is intended for course evaluation and for
  players who want to review their driving performance through simple telemetry
  charts.

- **Key features:**
  - Three-lap race format with countdown lights, HUD, minimap, speedometer,
    results screen, and podium display
  - Easy, Medium, and Hard difficulty modes with different obstacle and AI
    behavior settings
  - Player nitro system using `Shift` and nitro pads placed on the circuit
  - Persistent leaderboard stored in `leaderboard.csv`
  - Data pipeline from `stats/*.csv` to `visualize.py` and `reports/`
  - In-game telemetry viewer through `EmbeddedTelemetryViewer` in
    `visualize.py`

- **Screenshots:**  
  Gameplay and data screenshots are included in the repository.

  ![Race HUD](screenshots/gameplay/01_race_hud.png)
  ![Results screen](screenshots/gameplay/02_results_screen.png)
  ![Telemetry report](screenshots/visualization/01_full_report.png)

  Individual data visualization crops and explanations are listed in [screenshots/visualization/VISUALIZATION.md](screenshots/visualization/VISUALIZATION.md).

- **Original proposal (PDF):** [docs/PROJECT_PROPOSAL.pdf](docs/PROJECT_PROPOSAL.pdf)  

- **UML class diagram (PDF):** [docs/UML_Class_Diagram.pdf](docs/UML_Class_Diagram.pdf)  

- **Video presentation:** The final video shows gameplay, the statistics
  interface, the class structure, and the meaning of the charts/tables.

  **YouTube:** [Formula 67 project presentation](https://youtu.be/eiBPWpCaYYc)

---

## 2. Concept

### 2.1 Background

The project is inspired by classic top-down racing games and motorsport timing
systems. A racing game is a suitable scope for this course because it requires
object-oriented design, continuous user input, collision handling, game state
management, and measurable performance data.

### 2.2 Objectives

- Implement a playable three-lap racing mode with AI opponents and difficulty
  selection.
- Organize the main domain logic into classes such as car, track, race manager,
  obstacle, AI racer, logger, and leaderboard.
- Record at least five telemetry features into CSV files.
- Generate a statistical report that uses the recorded telemetry in tables and
  charts.
- Prepare the repository with the required description, README, license,
  attribution, screenshots, and PDF documents.

---

## 3. UML Class Diagram

The UML class diagram is provided as a separate PDF for readability:

**[docs/UML_Class_Diagram.pdf](docs/UML_Class_Diagram.pdf)**

The core relationship is that `PlayerCar` extends `Car`. The main game loop
creates and coordinates `Track`, `RaceManager`, `StatsLogger`, `Obstacle`,
`NitroPad`, and `AIRacer` objects.

---

## 4. Object-Oriented Programming Implementation

| Class | File | What it does |
|--------|------|----------------|
| **Car** | `car.py` | Stores position, speed, rotation, friction, sprite drawing, and mask collision. |
| **PlayerCar** | `car.py` | Adds nitro behavior, wall recovery, and player-specific reset state. |
| **Track** | `track.py` | Draws the circuit and handles border, finish-line, path, and checkpoint data. |
| **RaceManager** | `race.py` | Tracks laps, timers, race state, collisions, steering counts, nitro bursts, and race summaries. |
| **Obstacle** | `obstacle.py` | Represents cones, barrels, and oil; detects rectangle hits and applies penalties. |
| **NitroPad** | `obstacle.py` | Refills nitro with a cooldown after collection. |
| **AIRacer** | `ai_racer.py` | Follows a generated racing line and records lap/finish information. |
| **StatsLogger** | `stats.py` | Buffers telemetry rows and exports them to `stats/*.csv`. |
| **Leaderboard** | `stats.py` | Stores the 10 best lap times in `leaderboard.csv`. |
| **EmbeddedTelemetryViewer** | `visualize.py` | Displays the generated telemetry report inside the pygame window. |

Menu, HUD, and results screens are implemented in `screen_menu.py`,
`screen_results.py`, `hud.py`, and `race_intro.py`. The runtime glue is handled
by `world.py` and `main.py`. Configuration and assets are handled in
`settings.py` and `assets.py`, while standings calculations are placed in
`standings.py`.

---

## 5. Statistical Data

### 5.1 Data Recording Method

During gameplay, the logger stores records in memory and exports them to CSV at
the end of the race. Speed, position, input, and gap data are sampled at an
interval of approximately **0.2 seconds** (`SAMPLE_INTERVAL`). Steering,
collision, nitro, and cornering records are logged as event rows. The
visualization script reads the CSV files with pandas, aggregates the values, and
renders the final report image.

### 5.2 Data Features

| Feature | CSV / fields | Purpose |
|---------|----------------|------------------|
| Speed | `speed.csv` (`speed_px_s`, `timestamp`, `race_id`) | Line chart and histogram for pace review |
| Steering | `steering_event.csv`, `steering.csv` | Left/right steering distribution |
| Lap time | `lap_time.csv` | Best lap, consistency |
| Collision | `collision_event.csv`, `collision.csv` | Error analysis by race and difficulty |
| Nitro | `nitro_event.csv`, `nitro.csv` | Boost duration and average speed analysis |

After several races, the dataset contains enough rows for meaningful charts.
`seed_data.py` can be used to create additional demonstration data when needed.

---

## 6. Changes from the Original Proposal

Compared with the original proposal, the user interface and report layout were
improved during implementation. The AI path-following behavior was also tuned
to reduce stuck behavior and improve race flow. The core deliverables remain the
same: three-lap gameplay, CSV telemetry, and a multi-chart statistical report.

---

## 7. External Sources

- **Code libraries:** [pygame](https://www.pygame.org/), [matplotlib](https://matplotlib.org/), [pandas](https://pandas.pydata.org/) — versions in `requirements.txt`.  
- **Sprites / textures:** [ATTRIBUTION.md](ATTRIBUTION.md) (AI car art + reference links for track/grass).  
- **License for this repo:** [LICENSE](LICENSE) (MIT).

---

## Author and Run Command

**Piyapong Ausawarachan**

Run from the repository root:

```sh
python main.py
```

Additional setup and usage instructions are available in [README.md](README.md).
