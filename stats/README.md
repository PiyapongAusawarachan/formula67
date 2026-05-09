# Telemetry Data

This folder stores CSV telemetry produced by gameplay and by the optional
`seed_data.py` helper script.

| File group | Meaning |
|------------|---------|
| `speed.csv`, `position.csv`, `input_sample.csv`, `gap_sample.csv` | Sampled time-series telemetry |
| `steering_event.csv`, `collision_event.csv`, `nitro_event.csv`, `cornering_event.csv` | Event-based telemetry |
| `lap_time.csv`, `sector_split.csv`, `race_summary.csv`, `competitor.csv` | Race timing and classification data |
| `collision.csv`, `nitro.csv`, `steering.csv` | Summary/stat rows used by the report |

Run the following command from the repository root to regenerate the main report:

```sh
python visualize.py
```

The output image is written to `reports/telemetry_report.png`.
