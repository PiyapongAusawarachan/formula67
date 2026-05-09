# Visualization screenshots

These screenshots document the data component of Formula 67. The source data is written to `stats/*.csv` while the game runs, then `visualize.py` reads those CSV files and exports `reports/telemetry_report.png`.

## 1. Full telemetry report

![Full telemetry report](01_full_report.png)

This is the complete generated report page. It combines session summary cards, telemetry health checks, statistical tables, charts, and final race classification so the data can be reviewed in one place.

## 2. Telemetry channel overview

![Telemetry channel overview](02_channel_overview.png)

The channel overview checks whether each telemetry stream has enough rows for analysis. Speed, steering, lap, collision, nitro, position, sector, input, gap, and cornering channels are validated here.

## 3. Timing tables

![Timing tables](03_timing_tables.png)

The timing tables summarize important numeric values such as speed statistics, steering input totals, lap time statistics, and sector split timing. These tables make the raw CSV files readable without opening them manually.

## 4. Speed trace

![Speed trace](04_speed_trace.png)

The speed trace plots speed over race time. Straights create peaks, braking zones create dips, and collisions or grass contact show up as sudden drops.

## 5. Speed distribution

![Speed distribution](05_speed_distribution.png)

The histogram shows how often the player drove within each speed range. A tighter distribution means steadier pace, while a wide distribution suggests more braking, recovery, or inconsistent driving.

## 6. Boost scatter

![Boost scatter](06_boost_scatter.png)

This scatter plot compares nitro burst duration with average speed. It helps show whether boost is being used effectively on faster sections of the circuit.

## 7. Steering bias

![Steering bias](07_steering_bias.png)

The steering chart compares left and right input counts. This is useful for checking driving habits and whether one direction is being over-corrected.

## 8. Car XY path

![Car XY path](08_car_xy_path.png)

The XY path chart maps sampled player positions around the circuit and colors them by speed. It shows the driven racing line and highlights where the car slows down.

## 9. Gap trace

![Gap trace](09_gap_trace.png)

The gap trace records progress difference to the race leader. Higher values mean the player is behind; drops show recovery or closing the gap.

## 10. Race classification

![Race classification](10_race_classification.png)

The final classification table lists finishing order, best lap, race time, gap, and completed laps. This connects the telemetry summary back to the game result.

## Refreshing the report

From the repository root:

```sh
pip install -r requirements.txt
python visualize.py
```

The generated full report is saved to `reports/telemetry_report.png`.
