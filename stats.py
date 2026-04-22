"""StatsLogger and Leaderboard - data collection and ranking.

Collects 5 features (>=100 records each) and exports to CSV:
  1. Speed         - sampled every 0.2 s              -> speed.csv
  2. Steering      - every left/right key press        -> steering_event.csv
                     (plus per-race totals             -> steering.csv)
  3. Lap Time      - one record per completed lap      -> lap_time.csv
  4. Collision     - one record per individual hit     -> collision_event.csv
                     (plus per-race totals             -> collision.csv)
  5. Nitro burst   - one record per activation         -> nitro_event.csv
                     (plus per-race totals             -> nitro.csv)

Leaderboard maintains the top 10 best lap times using a sorting algorithm.
"""
import csv
import os
import time

class StatsLogger:
    SAMPLE_INTERVAL = 0.2

    _FEATURE_FILES = {
        "speed":            "speed.csv",
        "steering":         "steering.csv",
        "lap_time":         "lap_time.csv",
        "collision":        "collision.csv",
        "nitro":            "nitro.csv",
        "race_summary":     "race_summary.csv",
        "competitor":       "competitor.csv",
        "steering_event":   "steering_event.csv",
        "collision_event":  "collision_event.csv",
        "nitro_event":      "nitro_event.csv",
    }

    def __init__(self, file_path="stats"):
        self.file_path = file_path
        self.data_buffer = {
            "speed": [],
            "steering": [],
            "lap_time": [],
            "collision": [],
            "nitro": [],
        }
        self._last_sample_time = 0.0
        self._race_id = 0

        self._load_existing()

    def _load_existing(self):
        """Read every known CSV under ``file_path`` into the buffer."""
        if not os.path.isdir(self.file_path):
            return
        for feature, filename in self._FEATURE_FILES.items():
            path = os.path.join(self.file_path, filename)
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    rows = list(csv.DictReader(f))
            except (OSError, csv.Error):
                continue
            if not rows:
                continue
            self.data_buffer.setdefault(feature, []).extend(rows)
            for row in rows:
                rid = row.get("race_id")
                if rid is not None:
                    try:
                        self._race_id = max(self._race_id, int(float(rid)))
                    except (TypeError, ValueError):
                        pass

    def start_race(self):
        self._race_id += 1
        self._last_sample_time = time.time()

    def sample_speed(self, current_speed):
        """Sample player speed every SAMPLE_INTERVAL seconds."""
        now = time.time()
        if now - self._last_sample_time >= self.SAMPLE_INTERVAL:
            self._last_sample_time = now
            self.log_feature("speed", {
                "race_id": self._race_id,
                "timestamp": round(now, 3),
                "speed_px_s": round(current_speed, 3),
            })

    def log_feature(self, feature, record):
        if feature not in self.data_buffer:
            self.data_buffer[feature] = []
        self.data_buffer[feature].append(record)

    def log_lap(self, race_id, lap_number, lap_time):
        self.log_feature("lap_time", {
            "race_id": race_id,
            "lap_number": lap_number,
            "lap_time_s": round(lap_time, 3),
        })

    def log_collision_event(self, lap_number, source="obstacle"):
        """Record an individual collision event (hit obstacle or wall)."""
        self.log_feature("collision_event", {
            "race_id": self._race_id,
            "timestamp": round(time.time(), 3),
            "lap_number": lap_number,
            "source": source,
        })

    def log_nitro_event(self, lap_number, duration_s, avg_speed_px_s):
        """Record one completed nitro burst (activation -> deactivation)."""
        self.log_feature("nitro_event", {
            "race_id": self._race_id,
            "timestamp": round(time.time(), 3),
            "lap_number": lap_number,
            "duration_s": round(duration_s, 3),
            "avg_speed_px_s": round(avg_speed_px_s, 3),
        })

    def log_steering_event(self, direction):
        """Record one steering key press (every left/right input)."""
        self.log_feature("steering_event", {
            "race_id": self._race_id,
            "timestamp": round(time.time(), 3),
            "direction": direction,
        })

    def log_race_summary(self, summary):
        rid = self._race_id
        self.log_feature("steering", {
            "race_id": rid,
            "left_count": summary["steering_left"],
            "right_count": summary["steering_right"],
        })
        self.log_feature("collision", {
            "race_id": rid,
            "collision_count": summary["collisions"],
        })
        self.log_feature("nitro", {
            "race_id": rid,
            "nitro_duration_s": summary["nitro_duration"],
            "avg_speed_px_s": self._average_speed_for_race(rid),
        })

        best_lap = summary.get("best_lap") or 0.0
        self.log_feature("race_summary", {
            "race_id": rid,
            "total_time_s": summary["total_time"],
            "best_lap_s": round(best_lap, 3),
            "max_speed_px_per_frame": summary.get("max_speed", 0.0),
            "collisions": summary["collisions"],
            "nitro_duration_s": summary["nitro_duration"],
        })
        for i, lap_t in enumerate(summary["lap_times"], start=1):
            self.log_lap(rid, i, lap_t)

    def log_competitor_results(self, racers):
        """Record the finishing time and best lap of every competitor."""
        rid = self._race_id
        for r in racers:
            self.log_feature("competitor", {
                "race_id": rid,
                "name": r["name"],
                "rank": r.get("rank"),
                "finish_time_s": (round(r["finish_time"], 3)
                                  if r.get("finish_time") is not None
                                  else None),
                "best_lap_s": (round(r["best_lap"], 3)
                               if r.get("best_lap") is not None
                               else None),
                "lap_reached": r.get("lap"),
            })

    def _average_speed_for_race(self, race_id):
        samples = [r["speed_px_s"] for r in self.data_buffer["speed"]
                   if r.get("race_id") == race_id]
        if not samples:
            return 0.0
        return round(sum(samples) / len(samples), 3)

    def export_to_csv(self, output_dir=None):
        out_dir = output_dir or self.file_path
        os.makedirs(out_dir, exist_ok=True)
        written = []
        for feature, records in self.data_buffer.items():
            if not records:
                continue
            path = os.path.join(out_dir, f"{feature}.csv")
            fieldnames = list(records[0].keys())
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(records)
            written.append(path)
        return written

    def total_records(self):
        return {k: len(v) for k, v in self.data_buffer.items()}

class Leaderboard:
    """Top 10 best lap times. Uses insertion sort to keep entries ordered."""

    MAX_ENTRIES = 10

    def __init__(self, file_path="leaderboard.csv"):
        self.file_path = file_path
        self.entries = []
        self._load()

    def _load(self):
        if not os.path.exists(self.file_path):
            return
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.entries.append({
                        "name": row.get("name", "Player"),
                        "lap_time": float(row["lap_time"]),
                        "date": row.get("date", ""),
                    })
        except (KeyError, ValueError, OSError):
            self.entries = []
        self.entries = self._sort(self.entries)[: self.MAX_ENTRIES]

    @staticmethod
    def _sort(entries):
        """Insertion sort by lap_time ascending (lower is better)."""
        sorted_list = []
        for entry in entries:
            inserted = False
            for i, existing in enumerate(sorted_list):
                if entry["lap_time"] < existing["lap_time"]:
                    sorted_list.insert(i, entry)
                    inserted = True
                    break
            if not inserted:
                sorted_list.append(entry)
        return sorted_list

    def submit(self, name, lap_time):
        from datetime import datetime
        self.entries.append({
            "name": name,
            "lap_time": round(lap_time, 3),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
        self.entries = self._sort(self.entries)[: self.MAX_ENTRIES]
        self._save()

    def _save(self):
        with open(self.file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["name", "lap_time", "date"]
            )
            writer.writeheader()
            writer.writerows(self.entries)

    def top(self, n=10):
        return self.entries[:n]
