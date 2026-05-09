"""Fill ``stats/`` with synthetic CSV rows for demo / chart testing.

Commands:
  python seed_data.py
  python seed_data.py --races 50
  python seed_data.py --reset

Keeps races you already have, patches missing event files, adds fake races,
then runs ``visualize.py`` so ``reports/`` matches.
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import random
import shutil
import statistics
import time
from typing import Dict, List, Tuple

from settings import PATH

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATS_DIR = os.path.join(BASE_DIR, "stats")

DEFAULT_TARGET_RACES = 35
SAMPLE_INTERVAL = 0.2
LAP_BASELINE = 27.0
LAP_VARIATION = 4.5
RACE_GAP = 35
PEAK_SPEED_PX_FRAME = 7.2
NITRO_BURST_SPEED_BOOST = 1.8

random.seed(67)

def _read_csv(path: str) -> List[Dict[str, str]]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def _write_csv(path: str, rows: List[Dict], fieldnames: List[str]) -> None:
    if not rows:
        if os.path.exists(path):
            os.remove(path)
        return
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

def _to_float(v, d=0.0) -> float:
    try:
        return float(v) if v not in (None, "", "None") else d
    except (TypeError, ValueError):
        return d

def _to_int(v, d=0) -> int:
    try:
        return int(float(v)) if v not in (None, "", "None") else d
    except (TypeError, ValueError):
        return d

def _simulate_lap_times(num_laps: int = 3) -> List[float]:
    """Made-up lap times; lap 1 a bit slow on purpose."""
    times = []
    for lap in range(num_laps):
        bias = 0.6 if lap == 0 else (-0.4 if lap == num_laps - 1 else 0.0)
        t = max(20.0, random.gauss(LAP_BASELINE + bias, LAP_VARIATION / 2.2))
        times.append(round(t, 3))
    return times

def _simulate_speed_samples(start_ts: float, total_time_s: float
                            ) -> List[Tuple[float, float]]:
    """(timestamp, speed) points ~every SAMPLE_INTERVAL."""
    samples = []
    n = max(1, int(total_time_s / SAMPLE_INTERVAL))
    cruise = 4.4
    for i in range(n):
        ts = start_ts + i * SAMPLE_INTERVAL
        base = cruise + 1.6 * math.sin(i / 18.0)

        if (i % 80) > 70:
            base *= random.uniform(0.20, 0.55)

        if random.random() < 0.018:
            base *= random.uniform(1.30, 1.60)

        base += random.gauss(0, 0.35)
        spd = max(0.05, min(PEAK_SPEED_PX_FRAME * 1.05, base))
        samples.append((round(ts, 3), round(spd, 3)))
    return samples

def _simulate_steering_events(race_id: int, start_ts: float,
                              total_time_s: float
                              ) -> Tuple[List[Dict], int, int]:
    """Random left/right bursts spread over the race."""
    events = []
    t = start_ts
    end = start_ts + total_time_s
    while t < end:

        t += random.uniform(0.4, 1.6)
        if t >= end:
            break
        direction = random.choice(("left", "left", "right"))
        burst = random.randint(8, 22)
        for _ in range(burst):
            t += random.uniform(0.018, 0.045)
            if t >= end:
                break
            events.append({
                "race_id": race_id,
                "timestamp": round(t, 3),
                "direction": direction,
            })
    left = sum(1 for e in events if e["direction"] == "left")
    right = sum(1 for e in events if e["direction"] == "right")
    return events, left, right

def _simulate_collision_events(race_id: int, start_ts: float,
                               total_time_s: float, lap_count: int
                               ) -> List[Dict]:
    n_hits = random.randint(2, 9)
    events = []
    for _ in range(n_hits):
        when = start_ts + random.uniform(2.0, total_time_s - 1.0)
        lap = random.randint(1, lap_count)
        events.append({
            "race_id": race_id,
            "timestamp": round(when, 3),
            "lap_number": lap,
            "source": random.choice(("obstacle", "obstacle", "wall")),
        })
    events.sort(key=lambda e: e["timestamp"])
    return events

def _simulate_nitro_events(race_id: int, start_ts: float,
                           total_time_s: float, lap_count: int
                           ) -> List[Dict]:
    n_bursts = random.randint(3, 7)
    events = []
    for _ in range(n_bursts):
        when = start_ts + random.uniform(3.0, total_time_s - 2.0)
        duration = round(random.uniform(0.6, 2.8), 3)
        avg_speed = round(random.gauss(4.6, 0.55), 3)
        avg_speed = max(2.0, min(7.2, avg_speed))
        events.append({
            "race_id": race_id,
            "timestamp": round(when, 3),
            "lap_number": random.randint(1, lap_count),
            "duration_s": duration,
            "avg_speed_px_s": avg_speed,
        })
    events.sort(key=lambda e: e["timestamp"])
    return events

def _backfill_steering_events(steering_aggregates: List[Dict],
                              speed_rows: List[Dict],
                              max_per_race: int = 600) -> List[Dict]:
    """Turn steering.csv aggregates into fake per-press events."""
    out = []
    for agg in steering_aggregates:
        rid = _to_int(agg.get("race_id"))
        left = _to_int(agg.get("left_count"))
        right = _to_int(agg.get("right_count"))
        race_speeds = [r for r in speed_rows
                       if _to_int(r.get("race_id")) == rid]
        if not race_speeds:
            continue
        ts_start = _to_float(race_speeds[0].get("timestamp"))
        ts_end = _to_float(race_speeds[-1].get("timestamp"))

        total = left + right
        if total == 0:
            continue
        keep = min(total, max_per_race)
        scale = keep / total
        keep_left = int(round(left * scale))
        keep_right = keep - keep_left
        directions = (["left"] * keep_left) + (["right"] * keep_right)
        random.shuffle(directions)
        for i, d in enumerate(directions):
            ts = ts_start + (ts_end - ts_start) * (i + 0.5) / max(1, keep)
            out.append({
                "race_id": rid,
                "timestamp": round(ts, 3),
                "direction": d,
            })
    return out

def _backfill_collision_events(collision_aggregates: List[Dict],
                               speed_rows: List[Dict]) -> List[Dict]:
    out = []
    for agg in collision_aggregates:
        rid = _to_int(agg.get("race_id"))
        n = _to_int(agg.get("collision_count"))
        race_speeds = [r for r in speed_rows
                       if _to_int(r.get("race_id")) == rid]
        if not race_speeds or n <= 0:
            continue
        ts_start = _to_float(race_speeds[0].get("timestamp"))
        ts_end = _to_float(race_speeds[-1].get("timestamp"))
        for _ in range(n):
            ts = random.uniform(ts_start + 1, ts_end - 1)
            out.append({
                "race_id": rid,
                "timestamp": round(ts, 3),
                "lap_number": random.randint(1, 3),
                "source": random.choice(("obstacle", "obstacle", "wall")),
            })
    out.sort(key=lambda e: (e["race_id"], e["timestamp"]))
    return out

def _backfill_nitro_events(nitro_aggregates: List[Dict],
                           speed_rows: List[Dict]) -> List[Dict]:
    out = []
    for agg in nitro_aggregates:
        rid = _to_int(agg.get("race_id"))
        total_dur = _to_float(agg.get("nitro_duration_s"))
        avg_speed = _to_float(agg.get("avg_speed_px_s"), 4.0)
        race_speeds = [r for r in speed_rows
                       if _to_int(r.get("race_id")) == rid]
        if not race_speeds or total_dur <= 0:
            continue
        ts_start = _to_float(race_speeds[0].get("timestamp"))
        ts_end = _to_float(race_speeds[-1].get("timestamp"))

        n_bursts = random.randint(3, 6)
        durations = [random.uniform(0.4, 1.0) for _ in range(n_bursts)]
        scale = total_dur / sum(durations)
        durations = [round(d * scale, 3) for d in durations]
        for d in durations:
            ts = random.uniform(ts_start + 2, ts_end - 2)
            burst_avg = max(2.0, min(7.2, random.gauss(avg_speed * 1.5, 0.6)))
            out.append({
                "race_id": rid,
                "timestamp": round(ts, 3),
                "lap_number": random.randint(1, 3),
                "duration_s": d,
                "avg_speed_px_s": round(burst_avg, 3),
            })
    out.sort(key=lambda e: (e["race_id"], e["timestamp"]))
    return out

def seed(target_races: int = DEFAULT_TARGET_RACES,
         reset: bool = False) -> None:
    if reset and os.path.isdir(STATS_DIR):
        print(f"[seed] resetting {STATS_DIR}")
        shutil.rmtree(STATS_DIR)
    os.makedirs(STATS_DIR, exist_ok=True)

    race_sums   = _read_csv(os.path.join(STATS_DIR, "race_summary.csv"))
    laps_real   = _read_csv(os.path.join(STATS_DIR, "lap_time.csv"))
    speeds_real = _read_csv(os.path.join(STATS_DIR, "speed.csv"))
    steer_real  = _read_csv(os.path.join(STATS_DIR, "steering.csv"))
    coll_real   = _read_csv(os.path.join(STATS_DIR, "collision.csv"))
    nitro_real  = _read_csv(os.path.join(STATS_DIR, "nitro.csv"))
    competitor_real = _read_csv(os.path.join(STATS_DIR, "competitor.csv"))

    existing_max = (max((_to_int(r["race_id"]) for r in race_sums),
                        default=0))
    print(f"[seed] existing real races detected: {existing_max}")

    if existing_max >= target_races:
        print(f"[seed] dataset already has >= {target_races} races, "
              "nothing to do.")
        return

    steer_events_back = _backfill_steering_events(steer_real, speeds_real)
    coll_events_back  = _backfill_collision_events(coll_real, speeds_real)
    nitro_events_back = _backfill_nitro_events(nitro_real, speeds_real)

    out_race_sums = list(race_sums)
    out_laps      = list(laps_real)
    out_speeds    = list(speeds_real)
    out_steer     = list(steer_real)
    out_coll      = list(coll_real)
    out_nitro     = list(nitro_real)
    out_competitor = list(competitor_real)
    out_steer_evt = list(steer_events_back)
    out_coll_evt  = list(coll_events_back)
    out_nitro_evt = list(nitro_events_back)
    out_position = _read_csv(os.path.join(STATS_DIR, "position.csv"))
    out_sector = _read_csv(os.path.join(STATS_DIR, "sector_split.csv"))
    out_input = _read_csv(os.path.join(STATS_DIR, "input_sample.csv"))
    out_gap = _read_csv(os.path.join(STATS_DIR, "gap_sample.csv"))
    out_corner = _read_csv(os.path.join(STATS_DIR, "cornering_event.csv"))

    if out_speeds:
        last_ts = max(_to_float(r["timestamp"]) for r in out_speeds)
    else:
        last_ts = time.time() - target_races * 120
    cursor_ts = last_ts + 60

    ai_names = ["Verstappen", "Hamilton", "Leclerc", "Norris", "Player"]

    for race_id in range(existing_max + 1, target_races + 1):
        lap_times = _simulate_lap_times(num_laps=3)
        total_time = round(sum(lap_times), 3)
        best_lap = round(min(lap_times), 3)
        max_speed_frame = round(random.uniform(6.5, 7.4), 3)
        collision_count = random.randint(2, 9)
        nitro_total = round(random.uniform(4.0, 12.5), 2)

        out_race_sums.append({
            "race_id": race_id,
            "total_time_s": total_time,
            "best_lap_s": best_lap,
            "max_speed_px_per_frame": max_speed_frame,
            "collisions": collision_count,
            "nitro_duration_s": nitro_total,
        })

        for i, t in enumerate(lap_times, start=1):
            out_laps.append({
                "race_id": race_id,
                "lap_number": i,
                "lap_time_s": t,
            })

        speed_samples = _simulate_speed_samples(cursor_ts, total_time)
        for ts, spd in speed_samples:
            out_speeds.append({
                "race_id": race_id,
                "timestamp": ts,
                "speed_px_s": spd,
            })
        ang0 = random.uniform(0, 6.28)
        for ts, spd in speed_samples:
            ang = ang0 + (ts - cursor_ts) / max(total_time, 0.01) * math.pi * 5
            fx = 400 + 175 * math.cos(ang) + random.gauss(0, 14)
            fy = 380 + 130 * math.sin(ang * 1.03) + random.gauss(0, 14)
            pidx = int((ang % (2 * math.pi)) / (2 * math.pi) * len(PATH)) % len(PATH)
            lap_guess = min(3, max(1, int((ts - cursor_ts) / max(total_time / 3.5, 0.01)) + 1))
            out_position.append({
                "race_id": race_id,
                "timestamp": ts,
                "lap_number": lap_guess,
                "path_index": pidx,
                "x": round(fx, 1),
                "y": round(fy, 1),
                "speed_px_s": spd,
            })
            out_input.append({
                "race_id": race_id,
                "timestamp": ts,
                "throttle": 1 if spd > 2.5 else random.randint(0, 1),
                "brake": 1 if spd < 1.2 and random.random() < 0.2 else 0,
                "nitro": 1 if spd > 6.0 and random.random() < 0.12 else 0,
            })
            out_gap.append({
                "race_id": race_id,
                "timestamp": ts,
                "gap_progress": round(random.gauss(1.5, 7.0), 2),
            })
        for lap_n in (1, 2, 3):
            base = random.uniform(5.5, 8.0)
            for seg in (1, 2, 3):
                out_sector.append({
                    "race_id": race_id,
                    "lap_number": lap_n,
                    "sector_index": seg,
                    "split_s": round(base * random.uniform(0.55, 1.05), 3),
                })
                base *= random.uniform(0.75, 1.1)
        avg_speed_frame = round(
            statistics.mean(s for _, s in speed_samples), 3)

        steer_events, left_n, right_n = _simulate_steering_events(
            race_id, cursor_ts, total_time)
        out_steer_evt.extend(steer_events)
        for ev in steer_events:
            if random.random() < 0.4:
                out_corner.append({
                    "race_id": race_id,
                    "timestamp": ev["timestamp"],
                    "lap_number": random.randint(1, 3),
                    "direction": ev["direction"],
                    "speed_frame": round(random.uniform(2.4, 6.2), 3),
                })
        out_steer.append({
            "race_id": race_id,
            "left_count": left_n,
            "right_count": right_n,
        })

        coll_events = _simulate_collision_events(
            race_id, cursor_ts, total_time, lap_count=3)
        out_coll_evt.extend(coll_events)
        out_coll.append({
            "race_id": race_id,
            "collision_count": len(coll_events),
        })

        nitro_events = _simulate_nitro_events(
            race_id, cursor_ts, total_time, lap_count=3)
        out_nitro_evt.extend(nitro_events)
        race_nitro_total = round(
            sum(e["duration_s"] for e in nitro_events), 3)
        out_nitro.append({
            "race_id": race_id,
            "nitro_duration_s": race_nitro_total,
            "avg_speed_px_s": avg_speed_frame,
        })

        order = ai_names.copy()
        random.shuffle(order)
        for rank, name in enumerate(order, start=1):
            finish = round(total_time * random.uniform(0.97, 1.10), 3)
            best = round(best_lap * random.uniform(0.95, 1.10), 3)
            out_competitor.append({
                "race_id": race_id,
                "name": name,
                "rank": rank,
                "finish_time_s": finish,
                "best_lap_s": best,
                "lap_reached": 3,
            })

        cursor_ts += total_time + RACE_GAP

    _write_csv(os.path.join(STATS_DIR, "race_summary.csv"),
               out_race_sums,
               ["race_id", "total_time_s", "best_lap_s",
                "max_speed_px_per_frame", "collisions",
                "nitro_duration_s"])
    _write_csv(os.path.join(STATS_DIR, "lap_time.csv"),
               out_laps, ["race_id", "lap_number", "lap_time_s"])
    _write_csv(os.path.join(STATS_DIR, "speed.csv"),
               out_speeds, ["race_id", "timestamp", "speed_px_s"])
    _write_csv(os.path.join(STATS_DIR, "steering.csv"),
               out_steer, ["race_id", "left_count", "right_count"])
    _write_csv(os.path.join(STATS_DIR, "steering_event.csv"),
               out_steer_evt,
               ["race_id", "timestamp", "direction"])
    _write_csv(os.path.join(STATS_DIR, "collision.csv"),
               out_coll, ["race_id", "collision_count"])
    _write_csv(os.path.join(STATS_DIR, "collision_event.csv"),
               out_coll_evt,
               ["race_id", "timestamp", "lap_number", "source"])
    _write_csv(os.path.join(STATS_DIR, "nitro.csv"),
               out_nitro,
               ["race_id", "nitro_duration_s", "avg_speed_px_s"])
    _write_csv(os.path.join(STATS_DIR, "nitro_event.csv"),
               out_nitro_evt,
               ["race_id", "timestamp", "lap_number",
                "duration_s", "avg_speed_px_s"])
    _write_csv(os.path.join(STATS_DIR, "competitor.csv"),
               out_competitor,
               ["race_id", "name", "rank", "finish_time_s",
                "best_lap_s", "lap_reached"])
    _write_csv(os.path.join(STATS_DIR, "position.csv"),
               out_position,
               ["race_id", "timestamp", "lap_number", "path_index",
                "x", "y", "speed_px_s"])
    _write_csv(os.path.join(STATS_DIR, "sector_split.csv"),
               out_sector,
               ["race_id", "lap_number", "sector_index", "split_s"])
    _write_csv(os.path.join(STATS_DIR, "input_sample.csv"),
               out_input,
               ["race_id", "timestamp", "throttle", "brake", "nitro"])
    _write_csv(os.path.join(STATS_DIR, "gap_sample.csv"),
               out_gap,
               ["race_id", "timestamp", "gap_progress"])
    _write_csv(os.path.join(STATS_DIR, "cornering_event.csv"),
               out_corner,
               ["race_id", "timestamp", "lap_number", "direction",
                "speed_frame"])

    print()
    print("=" * 60)
    print(f"[seed] dataset now contains {target_races} races.")
    print(f"[seed] location: {STATS_DIR}")
    print("=" * 60)
    print(f"  race_summary       :  {len(out_race_sums):>6} records")
    print(f"  speed samples      :  {len(out_speeds):>6} records")
    print(f"  lap times          :  {len(out_laps):>6} records")
    print(f"  steering events    :  {len(out_steer_evt):>6} records")
    print(f"  collision events   :  {len(out_coll_evt):>6} records")
    print(f"  nitro burst events :  {len(out_nitro_evt):>6} records")
    print(f"  position samples   :  {len(out_position):>6} records")
    print(f"  sector splits      :  {len(out_sector):>6} records")
    print(f"  input samples      :  {len(out_input):>6} records")
    print(f"  gap samples        :  {len(out_gap):>6} records")
    print(f"  cornering events   :  {len(out_corner):>6} records")
    print("=" * 60)

def _maybe_render(open_browser: bool = True) -> None:
    """Call visualize again after writing CSVs."""
    try:
        from visualize import generate_report
    except ImportError:
        print("[seed] (visualize module unavailable - skipping report)")
        return
    out = generate_report(stats_dir=STATS_DIR,
                          out_dir=os.path.join(BASE_DIR, "reports"),
                          open_browser=open_browser)
    if out:
        print(f"[seed] dashboard rendered -> {out}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--races", type=int, default=DEFAULT_TARGET_RACES,
                        help="target total number of races (default: 35)")
    parser.add_argument("--reset", action="store_true",
                        help="WIPE existing stats/ folder before seeding")
    parser.add_argument("--no-render", action="store_true",
                        help="skip rendering the report at the end")
    args = parser.parse_args()

    seed(target_races=args.races, reset=args.reset)
    if not args.no_render:
        _maybe_render(open_browser=True)
