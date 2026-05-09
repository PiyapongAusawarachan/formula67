"""CSV telemetry (StatsLogger) and the lap-time leaderboard."""
import csv
import os
import time

# High-volume series: read only max race_id at startup (fast), merge on export.
_STREAM_FEATURES = frozenset({
    "speed", "steering_event", "collision_event", "nitro_event",
    "position", "sector_split", "input_sample", "gap_sample",
    "cornering_event",
})


def _scan_max_race_id(path):
    """One pass, low overhead (tuple rows, not dicts per line)."""
    mx = 0
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                return 0
            try:
                rid_idx = header.index("race_id")
            except ValueError:
                return 0
            for row in reader:
                if len(row) <= rid_idx:
                    continue
                try:
                    mx = max(mx, int(float(row[rid_idx])))
                except (TypeError, ValueError):
                    pass
    except OSError:
        return 0
    return mx


def _merge_fieldnames(rows_a, rows_b):
    order = []
    seen = set()
    for block in (rows_a, rows_b):
        for row in block:
            for k in row:
                if k not in seen:
                    seen.add(k)
                    order.append(k)
    return order


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
        "position":         "position.csv",
        "sector_split":     "sector_split.csv",
        "input_sample":     "input_sample.csv",
        "gap_sample":       "gap_sample.csv",
        "cornering_event":  "cornering_event.csv",
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
        """Load prior CSV rows from disk into memory."""
        if not os.path.isdir(self.file_path):
            return
        for feature, filename in self._FEATURE_FILES.items():
            path = os.path.join(self.file_path, filename)
            if not os.path.exists(path):
                continue
            if feature in _STREAM_FEATURES:
                self._race_id = max(self._race_id, _scan_max_race_id(path))
                self.data_buffer.setdefault(feature, [])
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

    @property
    def race_id(self):
        return self._race_id

    def start_race(self):
        self._race_id += 1
        self._last_sample_time = time.time()

    def telemetry_bundle(
            self,
            current_speed,
            cx,
            cy,
            path_idx,
            lap_number,
            throttle,
            brake,
            nitro_on,
            gap_progress,
    ):
        """Speed + on-track position + pedals + gap to leader on one clock."""
        now = time.time()
        if now - self._last_sample_time < self.SAMPLE_INTERVAL:
            return
        self._last_sample_time = now
        rid = self._race_id
        ts = round(now, 3)
        self.log_feature("speed", {
            "race_id": rid, "timestamp": ts,
            "speed_px_s": round(current_speed, 3),
        })
        self.log_feature("position", {
            "race_id": rid, "timestamp": ts, "lap_number": lap_number,
            "path_index": path_idx, "x": round(cx, 1), "y": round(cy, 1),
            "speed_px_s": round(current_speed, 3),
        })
        t_val = 1 if throttle else 0
        b_val = 1 if brake else 0
        n_val = 1 if nitro_on else 0
        self.log_feature("input_sample", {
            "race_id": rid, "timestamp": ts,
            "throttle": t_val, "brake": b_val, "nitro": n_val,
        })
        self.log_feature("gap_sample", {
            "race_id": rid, "timestamp": ts,
            "gap_progress": gap_progress,
        })

    def log_sector_split(self, race_id, lap_number, sector_index, split_s):
        self.log_feature("sector_split", {
            "race_id": race_id,
            "lap_number": lap_number,
            "sector_index": sector_index,
            "split_s": split_s,
        })

    def log_cornering_event(self, lap_number, direction, speed_frame):
        self.log_feature("cornering_event", {
            "race_id": self._race_id,
            "timestamp": round(time.time(), 3),
            "lap_number": lap_number,
            "direction": direction,
            "speed_frame": round(speed_frame, 3),
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
        """One row per bump (wall or obstacle)."""
        self.log_feature("collision_event", {
            "race_id": self._race_id,
            "timestamp": round(time.time(), 3),
            "lap_number": lap_number,
            "source": source,
        })

    def log_nitro_event(self, lap_number, duration_s, avg_speed_px_s):
        """Called when a nitro burst ends (duration + average speed)."""
        self.log_feature("nitro_event", {
            "race_id": self._race_id,
            "timestamp": round(time.time(), 3),
            "lap_number": lap_number,
            "duration_s": round(duration_s, 3),
            "avg_speed_px_s": round(avg_speed_px_s, 3),
        })

    def log_steering_event(self, direction):
        """One row per left/right key press."""
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
        """Store finish time / best lap for each AI name."""
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
        speed_rows = self.data_buffer.get("speed") or []
        samples = [r["speed_px_s"] for r in speed_rows
                   if r.get("race_id") == race_id]
        if not samples:
            return 0.0
        return round(sum(samples) / len(samples), 3)

    def export_to_csv(self, output_dir=None):
        out_dir = output_dir or self.file_path
        os.makedirs(out_dir, exist_ok=True)
        written = []
        for feature, records in self.data_buffer.items():
            path = os.path.join(out_dir, f"{feature}.csv")
            if feature in _STREAM_FEATURES:
                existing = []
                if os.path.exists(path):
                    try:
                        with open(path, newline="", encoding="utf-8") as f:
                            existing = list(csv.DictReader(f))
                    except (OSError, csv.Error):
                        existing = []
                if not existing and not records:
                    continue
                all_rows = existing + records
                fieldnames = _merge_fieldnames(existing, records)
            else:
                if not records:
                    continue
                all_rows = records
                fieldnames = list(records[0].keys())
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_rows)
            written.append(path)
        return written

    def total_records(self):
        return {k: len(v) for k, v in self.data_buffer.items()}

class Leaderboard:
    """Top 10 laps, read/write ``leaderboard.csv``."""

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
        """Keep entries sorted fastest-first (insertion sort; N is tiny)."""
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
