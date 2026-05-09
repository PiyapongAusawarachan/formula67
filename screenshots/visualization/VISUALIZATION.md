# Visualization Screenshots

This document explains the data visualization screenshots included with
Formula 67. During gameplay, telemetry is written to `stats/*.csv`. The
`visualize.py` script reads those CSV files and exports the complete report to
`reports/telemetry_report.png`.

## 1. Full Telemetry Report

![Full telemetry report](01_full_report.png)

This screenshot shows the complete generated report. It combines session
summary cards, telemetry coverage checks, statistical tables, charts, and final
race classification so that the recorded data can be reviewed in one place.

## 2. Telemetry Channel Overview

![Telemetry channel overview](02_channel_overview.png)

The channel overview verifies that each telemetry stream contains usable data.
The report checks speed, steering, lap, collision, nitro, position, sector,
input, gap, and cornering channels.

## 3. Timing Tables

![Timing tables](03_timing_tables.png)

The timing tables summarize important numeric values, including speed
statistics, steering totals, lap-time statistics, and sector split timing. These
tables make the CSV data readable without opening each file manually.

## 4. Speed Trace

![Speed trace](04_speed_trace.png)

The speed trace plots speed over race time. Straights usually create peaks,
braking zones create dips, and collisions or grass contact appear as sudden
drops.

## 5. Speed Distribution

![Speed distribution](05_speed_distribution.png)

The histogram shows how often the player drove within each speed range. A
tighter distribution indicates steadier pace, while a wider distribution may
indicate frequent braking, recovery, or inconsistent driving.

## 6. Boost Scatter

![Boost scatter](06_boost_scatter.png)

This scatter plot compares nitro burst duration with average speed. It helps
evaluate whether boost was used effectively on faster sections of the circuit.

## 7. Steering Bias

![Steering bias](07_steering_bias.png)

The steering chart compares left and right input counts. It helps identify
driving habits and possible over-correction in one direction.

## 8. Car XY Path

![Car XY path](08_car_xy_path.png)

The XY path chart maps sampled player positions around the circuit and colors
them by speed. It shows the driven racing line and highlights where the car
slows down.

## 9. Gap Trace

![Gap trace](09_gap_trace.png)

The gap trace records progress difference to the race leader. Higher values
mean the player is farther behind; downward movement indicates recovery or a
closing gap.

## 10. Race Classification

![Race classification](10_race_classification.png)

The final classification table lists finishing order, best lap, race time, gap,
and completed laps. This connects the telemetry summary with the game result.

## Regenerating the Report

From the repository root:

```sh
pip install -r requirements.txt
python visualize.py
```

The full report is saved to `reports/telemetry_report.png`.
