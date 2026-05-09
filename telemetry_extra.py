"""Extra logging: sector splits via track checkpoints, path index, etc."""
from typing import List, Tuple

# Squared distance threshold (px) to count hitting a sector beacon
_SECTOR_HIT_R2 = 75 * 75
_COOLDOWN_S = 0.45


def nearest_path_index(player_car, path) -> int:
    cx = player_car.x + player_car.img.get_width() / 2
    cy = player_car.y + player_car.img.get_height() / 2
    best_i = 0
    best_d = float("inf")
    for i, (qx, qy) in enumerate(path):
        d = (cx - qx) ** 2 + (cy - qy) ** 2
        if d < best_d:
            best_d = d
            best_i = i
    return best_i


class SectorTimer:
    """Three sector beacons = points on ``track.checkpoints`` in order."""

    def __init__(self):
        self._next = 0
        self._split_t0 = None
        self._cool_until = 0.0

    def on_race_start(self, time_s: float) -> None:
        self._next = 0
        self._split_t0 = time_s
        self._cool_until = time_s + 0.5

    def on_new_lap(self, time_s: float) -> None:
        self._next = 0
        self._split_t0 = time_s
        self._cool_until = time_s + _COOLDOWN_S

    def tick(
            self,
            player_car,
            checkpoints: List[Tuple[float, float]],
            lap: int,
            race_id: int,
            stats_logger,
            time_s: float,
    ) -> None:
        if stats_logger is None or self._split_t0 is None:
            return
        if time_s < self._cool_until:
            return
        if self._next >= len(checkpoints):
            return

        cx = player_car.x + player_car.img.get_width() / 2
        cy = player_car.y + player_car.img.get_height() / 2
        tx, ty = checkpoints[self._next]
        if (cx - tx) ** 2 + (cy - ty) ** 2 <= _SECTOR_HIT_R2:
            split_s = round(time_s - self._split_t0, 3)
            stats_logger.log_sector_split(race_id, lap, self._next + 1,
                                         split_s)
            self._split_t0 = time_s
            self._next += 1
            self._cool_until = time_s + _COOLDOWN_S


def gap_progress_units(standings, player_progress: float) -> float:
    """Difference in ``progress`` vs current P1 (negative = ahead)."""
    if not standings:
        return 0.0
    leader_p = standings[0].get("progress", 0)
    return round(float(leader_p - player_progress), 2)
