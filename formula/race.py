"""RaceManager class - controls game state, lap timing, and race flow."""
import time

_NITRO_BURST_MIN_SECONDS = 0.05

class RaceManager:
    TOTAL_LAPS = 3

    def __init__(self):
        self.timer = 0.0
        self.current_lap = 0
        self.is_game_over = False
        self.player_finished = False
        self.player_finish_time = None
        self.started = False
        self._race_start_time = 0.0
        self._lap_start_time = 0.0
        self.lap_times = []
        self.collision_count = 0
        self.nitro_duration = 0.0
        self.steering_left_count = 0
        self.steering_right_count = 0
        self.max_speed = 0.0

        self._nitro_burst_active = False
        self._nitro_burst_start = 0.0
        self._nitro_burst_speed_sum = 0.0
        self._nitro_burst_speed_count = 0
        self.nitro_burst_count = 0

    def start_race(self):
        self.started = True
        self.is_game_over = False
        self.player_finished = False
        self.player_finish_time = None
        self._race_start_time = time.time()
        self._lap_start_time = self._race_start_time
        self.current_lap = 1

    def get_race_time(self):
        if not self.started:
            return 0.0
        if self.player_finished and self.player_finish_time is not None:
            return self.player_finish_time
        return time.time() - self._race_start_time

    def get_current_lap_time(self):
        if not self.started or self.player_finished:
            return 0.0
        return time.time() - self._lap_start_time

    def track_lap_time(self):
        """Called when player crosses the finish line correctly."""
        now = time.time()
        lap_time = now - self._lap_start_time
        self.lap_times.append(round(lap_time, 3))
        self._lap_start_time = now

        if self.current_lap >= self.TOTAL_LAPS:
            self.player_finished = True
            self.player_finish_time = now - self._race_start_time
            return True
        self.current_lap += 1
        return False

    def end_race(self):
        """Called when every racer (player + AIs) has finished."""
        self.is_game_over = True

    def update_max_speed(self, vel):
        if abs(vel) > self.max_speed:
            self.max_speed = abs(vel)

    def register_collision(self):
        self.collision_count += 1

    def add_nitro_time(self, dt):
        self.nitro_duration += dt

    def track_nitro_burst(self, active, current_speed_px_per_frame):
        """Detect nitro activation/deactivation transitions.

        Returns ``(burst_just_ended, duration_s, avg_speed_px_per_frame)``
        every time the player releases nitro.  When still mid-burst (or
        not active at all), returns ``(False, 0.0, 0.0)``.
        """
        now = time.time()
        if active:
            if not self._nitro_burst_active:
                self._nitro_burst_active = True
                self._nitro_burst_start = now
                self._nitro_burst_speed_sum = 0.0
                self._nitro_burst_speed_count = 0
            self._nitro_burst_speed_sum += abs(current_speed_px_per_frame)
            self._nitro_burst_speed_count += 1
            return (False, 0.0, 0.0)

        if self._nitro_burst_active:
            self._nitro_burst_active = False
            duration = now - self._nitro_burst_start
            avg = (self._nitro_burst_speed_sum / self._nitro_burst_speed_count
                   if self._nitro_burst_speed_count else 0.0)
            if duration >= _NITRO_BURST_MIN_SECONDS:
                self.nitro_burst_count += 1
                return (True, duration, avg)
        return (False, 0.0, 0.0)

    def register_steering(self, direction):
        if direction == "left":
            self.steering_left_count += 1
        elif direction == "right":
            self.steering_right_count += 1

    def reset_game(self):
        self.timer = 0.0
        self.current_lap = 0
        self.is_game_over = False
        self.player_finished = False
        self.player_finish_time = None
        self.started = False
        self._race_start_time = 0.0
        self._lap_start_time = 0.0
        self.lap_times = []
        self.collision_count = 0
        self.nitro_duration = 0.0
        self.steering_left_count = 0
        self.steering_right_count = 0
        self.max_speed = 0.0
        self._nitro_burst_active = False
        self._nitro_burst_start = 0.0
        self._nitro_burst_speed_sum = 0.0
        self._nitro_burst_speed_count = 0
        self.nitro_burst_count = 0

    def race_summary(self):
        return {
            "total_time": round(sum(self.lap_times), 3),
            "lap_times": list(self.lap_times),
            "best_lap": min(self.lap_times) if self.lap_times else None,
            "collisions": self.collision_count,
            "nitro_duration": round(self.nitro_duration, 2),
            "steering_left": self.steering_left_count,
            "steering_right": self.steering_right_count,
            "max_speed": round(self.max_speed, 3),
        }
