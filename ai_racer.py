"""AI cars: follow personalized racing lines with border-aware steering."""
import math
import time

import pygame

from assets import track_to_screen

_MIN_AI_LAP_SECONDS = 4.0


class AIRacer:
    """CPU car: steers toward a point a bit down the path (stops darting on tight nodes)."""

    def __init__(self, name, image, max_vel, rotation_vel, path,
                 start_offset=0, lateral_offset=0, longitudinal_offset=0,
                 start_pos=None, accent_color=(200, 200, 200),
                 racing_line_offset=0, lookahead_bias=0,
                 border_mask=None, safety_margin=10,
                 apex_strength=1.0, corner_aggression=1.0,
                 accel_rate=0.07, line_variance=5.0,
                 avoidance_strength=1.0):
        self.name = name
        self.img = image
        self.accent_color = accent_color
        self.max_vel = max_vel
        self.rotation_vel = rotation_vel
        self.path = path
        self.start_offset = start_offset
        self.lateral_offset = lateral_offset
        self.longitudinal_offset = longitudinal_offset

        self.start_pos = start_pos

        self.racing_line_offset = racing_line_offset

        self.lookahead_bias = lookahead_bias

        self.border_mask = border_mask
        self.safety_margin = safety_margin

        self.apex_strength = apex_strength

        self.corner_aggression = corner_aggression
        self.accel_rate = accel_rate
        self.line_variance = line_variance
        self.avoidance_strength = avoidance_strength
        self.driver_seed = sum(ord(ch) for ch in name) + int(
            racing_line_offset * 17)
        self.personal_path = self._build_personal_path(racing_line_offset)
        self._start_index = self._personal_index(start_offset)

        self.vel = 0
        self.angle = 0
        self.current_point = (self._start_index + 3) % len(self.personal_path)
        self.lap = 1
        self.finish_time = None
        self.finish_order = None
        self.race_start_time = None
        self.lap_times = []
        self._lap_start_time = None
        self._points_since_lap_start = 0
        self._finish_was_on = False

        self._rotated_cache = {}
        self._mask_step = 6
        self._tick = 0
        self._last_progress_point = self.current_point
        self._stall_frames = 0

        self._set_start_position()

    def _personal_index(self, original_index):
        if not self.personal_path:
            return 0
        if not self.path:
            return 0
        return int((original_index % len(self.path)) / len(self.path)
                   * len(self.personal_path)) % len(self.personal_path)

    def _nearest_personal_index(self, x, y):
        if not self.personal_path:
            return 0
        return min(
            range(len(self.personal_path)),
            key=lambda i: ((self.personal_path[i][0] - x) ** 2
                           + (self.personal_path[i][1] - y) ** 2),
        )

    def _build_personal_path(self, bias_offset):
        """Densify PATH and build a unique, safe racing line for this driver."""
        n = len(self.path)
        if n == 0:
            return []

        TARGET_DENSE = 360
        total_len = self._path_total_length()
        dense = []

        for i in range(n):
            a = self.path[i]
            b = self.path[(i + 1) % n]
            seg_len = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
            steps = max(4, int(round(TARGET_DENSE * seg_len / total_len)))
            for k in range(steps):
                t = k / steps
                dense.append((a[0] + (b[0] - a[0]) * t,
                              a[1] + (b[1] - a[1]) * t))
        dn = len(dense)

        for _ in range(5):
            smoothed_dense = []
            for i, cur in enumerate(dense):
                prev = dense[(i - 1) % dn]
                nxt = dense[(i + 1) % dn]
                sx = (prev[0] + cur[0] * 2.0 + nxt[0]) * 0.25
                sy = (prev[1] + cur[1] * 2.0 + nxt[1]) * 0.25
                if self._point_inside_track(sx, sy):
                    smoothed_dense.append((sx, sy))
                else:
                    smoothed_dense.append(cur)
            dense = smoothed_dense

        tangents = []
        perps = []
        for i in range(dn):
            prev = dense[(i - 1) % dn]
            nxt = dense[(i + 1) % dn]
            tx = nxt[0] - prev[0]
            ty = nxt[1] - prev[1]
            L = math.hypot(tx, ty) or 1.0
            tangents.append((tx / L, ty / L))
            perps.append((-ty / L, tx / L))

        sample_gap = max(3, dn // 60)
        raw_curv = []
        for i in range(dn):
            t0 = tangents[(i - sample_gap) % dn]
            t1 = tangents[(i + sample_gap) % dn]
            cz = t0[0] * t1[1] - t0[1] * t1[0]
            raw_curv.append(cz)

        win = max(4, dn // 30)
        smoothed = []
        for i in range(dn):
            s = 0.0
            for k in range(-win, win + 1):
                s += raw_curv[(i + k) % dn]
            smoothed.append(s / (2 * win + 1))

        max_curv = max((abs(c) for c in smoothed), default=1.0) or 1.0

        APEX_PIXELS = 14.0
        phase = (self.driver_seed % 997) / 997.0 * math.tau

        out = []
        for di, (base_x, base_y) in enumerate(dense):
            curv_norm = smoothed[di] / max_curv
            ahead = smoothed[(di + max(3, dn // 70)) % dn] / max_curv
            corner_load = min(1.0, abs(curv_norm) * 1.35)
            apex_offset = (
                curv_norm * 0.76 + ahead * 0.24
            ) * APEX_PIXELS * self.apex_strength

            straight_factor = 1.0 - corner_load
            lane_bias = bias_offset * (0.35 + straight_factor * 0.65)
            flow = math.sin((di / dn) * math.tau * 2.35 + phase)
            flow += 0.45 * math.sin((di / dn) * math.tau * 4.7 + phase * 0.37)
            personal_flow = flow * self.line_variance * (
                0.32 + straight_factor * 0.68)
            target = apex_offset + lane_bias + personal_flow
            target = max(-18.0, min(18.0, target))

            px, py = perps[di]
            safe = self._clamp_offset(base_x, base_y, px, py, target)
            out.append((base_x + px * safe, base_y + py * safe))
        return out

    def _path_total_length(self):
        """Perimeter of the centreline (cached)."""
        cached = getattr(self, "_cached_path_len", None)
        if cached is not None:
            return cached
        total = 0.0
        n = len(self.path)
        for i in range(n):
            a = self.path[i]
            b = self.path[(i + 1) % n]
            total += math.hypot(b[0] - a[0], b[1] - a[1])
        self._cached_path_len = total or 1.0
        return self._cached_path_len

    def _point_inside_track(self, x, y, margin=None):
        """True if a small ring around (x,y) isn't touching the grass mask."""
        if self.border_mask is None:
            return True
        ix, iy = int(x), int(y)
        r = max(1, int(self.safety_margin if margin is None else margin))

        wide = int(r * 1.35)
        samples = [(0, 0), (r, 0), (-r, 0), (0, r), (0, -r),
                   (wide, wide), (-wide, -wide),
                   (wide, -wide), (-wide, wide)]
        mw, mh = self.border_mask.get_size()
        for dx, dy in samples:
            sx, sy = ix + dx, iy + dy
            if sx < 0 or sy < 0 or sx >= mw or sy >= mh:
                return False
            if self.border_mask.get_at((sx, sy)):
                return False
        return True

    def _clamp_offset(self, base_x, base_y, px, py, requested):
        """Shrink side offset until the target sits on asphalt again."""
        if self.border_mask is None or requested == 0:
            return requested
        sign = 1 if requested > 0 else -1
        magnitude = abs(requested)
        while magnitude > 0:
            x = base_x + px * magnitude * sign
            y = base_y + py * magnitude * sign
            if self._point_inside_track(x, y):
                return magnitude * sign
            magnitude -= 1
        return 0

    def best_lap_time(self):
        return min(self.lap_times) if self.lap_times else None

    def _set_start_position(self):

        if self.start_pos is not None:

            sx = self.start_pos[0] + self.img.get_width() / 2
            sy = self.start_pos[1] + self.img.get_height() / 2

            start_index = self._nearest_personal_index(sx, sy)
            aim_index = (start_index + 8) % len(self.personal_path)
            tx, ty = self.personal_path[aim_index]
            x_diff = tx - sx
            y_diff = ty - sy
        else:
            sx, sy = self.personal_path[self._start_index]
            nx, ny = self.personal_path[
                (self._start_index + 1) % len(self.personal_path)]
            x_diff = nx - sx
            y_diff = ny - sy

        if y_diff == 0:
            desired = math.pi / 2 if x_diff > 0 else -math.pi / 2
        else:
            desired = math.atan(x_diff / y_diff)
        if y_diff > 0:
            desired += math.pi

        self.angle = math.degrees(desired)

        length = math.hypot(x_diff, y_diff) or 1.0
        fwd_x = x_diff / length
        fwd_y = y_diff / length
        perp_x = -y_diff / length
        perp_y = x_diff / length

        if self.lateral_offset:
            sx += perp_x * self.lateral_offset
            sy += perp_y * self.lateral_offset
        if self.longitudinal_offset:
            sx += fwd_x * self.longitudinal_offset
            sy += fwd_y * self.longitudinal_offset

        if self.start_pos is not None:
            self._start_index = self._nearest_personal_index(sx, sy)
            self.current_point = (self._start_index + 8) % len(self.personal_path)
            tx, ty = self.personal_path[self.current_point]
            x_diff = tx - sx
            y_diff = ty - sy
            if y_diff == 0:
                desired = math.pi / 2 if x_diff > 0 else -math.pi / 2
            else:
                desired = math.atan(x_diff / y_diff)
            if y_diff > 0:
                desired += math.pi
            self.angle = math.degrees(desired)

        self.x = sx - self.img.get_width() / 2
        self.y = sy - self.img.get_height() / 2

    def reset(self):
        self.vel = 0
        self.lap = 1
        self.current_point = (self._start_index + 3) % len(self.personal_path)
        self.finish_time = None
        self.finish_order = None
        self.race_start_time = None
        self.lap_times = []
        self._lap_start_time = None
        self._points_since_lap_start = 0
        self._finish_was_on = False
        self._tick = 0
        self._last_progress_point = self.current_point
        self._stall_frames = 0
        self._set_start_position()

    def start(self, race_start_time):
        self.race_start_time = race_start_time
        self._lap_start_time = race_start_time
        self.vel = 0
        self._finish_was_on = False

    def progress_score(self):
        """Rough distance into the race (for sorting HUD)."""
        scaled_point = self.current_point / max(1, len(self.personal_path))
        return self.lap * len(self.path) + scaled_point * len(self.path)

    def update(self, total_laps):
        if self.finish_time is not None:
            return
        if self.race_start_time is None:
            return
        self._tick += 1
        if self._tick % 18 == 0:
            self._recover_from_border()

        self._advance_passed_waypoints(total_laps)

        steer_diff = self._steer_towards_lookahead()

        turn_lift = abs(steer_diff) / (158.0 * self.corner_aggression)
        turn_factor = max(0.84, 1.0 - turn_lift)
        target_vel = self.max_vel * turn_factor

        border_risk = self._border_risk()
        if border_risk:
            target_vel *= 0.78 if border_risk >= 1.0 else 0.94
            self._nudge_back_to_path(
                (1.35 + border_risk * 0.55) * self.avoidance_strength)

        if self.vel < target_vel:
            accel = self.accel_rate * (1.45 if abs(steer_diff) > 38 else 1.0)
            self.vel = min(self.vel + accel, target_vel)
        else:
            self.vel = max(self.vel - 0.18, target_vel)

        self._move()
        self._recover_from_border()
        self._unstick_if_needed(total_laps)

    def handle_finish_line(self, finish_collision, total_laps,
                           finish_order_cb=None):
        if self.finish_time is not None:
            self._finish_was_on = finish_collision is not None
            return

        on_finish = finish_collision is not None
        if on_finish and not self._finish_was_on:
            if finish_collision[1] != 0:
                self._record_finish_lap(total_laps, finish_order_cb)
        self._finish_was_on = on_finish

    def _record_finish_lap(self, total_laps, finish_order_cb=None):
        if self.race_start_time is None or self._lap_start_time is None:
            return False

        now = time.time()
        lap_time = now - self._lap_start_time
        if lap_time < _MIN_AI_LAP_SECONDS:
            return False

        self.lap_times.append(round(lap_time, 3))
        self._lap_start_time = now
        self._points_since_lap_start = 0
        self.lap += 1
        if self.lap > total_laps:
            self.finish_time = now - self.race_start_time
            if self.finish_order is None and finish_order_cb is not None:
                self.finish_order = finish_order_cb()
            self.vel = 0
            return True
        return False

    def _border_risk(self):
        """Return 0..1 for current/future border contact risk."""
        if self.border_mask is None:
            return 0.0
        cx, cy = self._car_center()
        if not self._point_inside_track(cx, cy, margin=5):
            return 0.85
        radians = math.radians(self.angle)
        sin_a = math.sin(radians)
        cos_a = math.cos(radians)
        for dist in (max(12.0, self.vel * 2.8),
                     max(20.0, self.vel * 4.0)):
            px = cx - sin_a * dist
            py = cy - cos_a * dist
            if not self._point_inside_track(px, py, margin=4):
                return 0.34
        return 0.0

    def _nudge_back_to_path(self, strength=2.0):
        """Yaw back toward the centre if we're scraping the wall."""
        tx, ty = self.personal_path[self.current_point]
        diff = self._signed_angle_to(tx, ty)

        step = min(self.rotation_vel * strength, abs(diff))
        if diff > 0:
            self.angle -= step
        else:
            self.angle += step

    def _recover_from_border(self):
        """Pull the AI centre back onto legal asphalt if it drifts off-line."""
        if self.border_mask is None:
            return False
        cx, cy = self._car_center()
        if self._point_inside_track(cx, cy, margin=4):
            return False

        old_x, old_y = self.x, self.y
        target = self.personal_path[self.current_point]
        best = None
        best_score = None
        for radius in range(2, 42, 2):
            for deg in range(0, 360, 18):
                rad = math.radians(deg)
                nx = old_x + math.cos(rad) * radius
                ny = old_y + math.sin(rad) * radius
                cx = nx + self.img.get_width() / 2
                cy = ny + self.img.get_height() / 2
                if not self._point_inside_track(cx, cy, margin=5):
                    continue
                score = ((cx - target[0]) ** 2 + (cy - target[1]) ** 2
                         + radius * 14)
                if best_score is None or score < best_score:
                    best_score = score
                    best = (nx, ny)
            if best is not None:
                break

        if best is None:
            self.vel = 0
            return False

        self.x, self.y = best
        self.vel = max(self.vel * 0.88, min(self.max_vel * 0.52, 1.85))
        self._nudge_back_to_path(2.4)
        return True

    def _unstick_if_needed(self, total_laps):
        """Keep collision/border recovery from turning into a permanent crawl."""
        if self.current_point != self._last_progress_point:
            self._last_progress_point = self.current_point
            self._stall_frames = 0
            return
        if self.vel > 1.25:
            self._stall_frames = 0
            return

        self._stall_frames += 1
        if self._stall_frames < 16:
            return

        tx, ty = self.personal_path[self.current_point]
        diff = self._signed_angle_to(tx, ty)
        step = min(self.rotation_vel * 2.2, abs(diff))
        if diff > 0:
            self.angle -= step
        else:
            self.angle += step
        self.vel = max(self.vel, min(self.max_vel * 0.38, 1.7))
        self._stall_frames = 0

    def _car_center(self):
        return (self.x + self.img.get_width() / 2,
                self.y + self.img.get_height() / 2)

    def _signed_angle_to(self, target_x, target_y):
        cx, cy = self._car_center()
        x_diff = target_x - cx
        y_diff = target_y - cy

        if y_diff == 0:
            desired = math.pi / 2 if x_diff > 0 else -math.pi / 2
        else:
            desired = math.atan(x_diff / y_diff)
        if y_diff > 0:
            desired += math.pi

        diff = self.angle - math.degrees(desired)
        while diff > 180:
            diff -= 360
        while diff < -180:
            diff += 360
        return diff

    def _steer_towards_lookahead(self):
        """Pick a point ~lookahead units ahead and rotate toward it."""
        cx, cy = self._car_center()

        lookahead = 54 + self.vel * 7.5 + self.lookahead_bias
        lookahead = max(42, lookahead)

        idx = self.current_point
        tx, ty = self.personal_path[idx]
        accumulated = math.hypot(tx - cx, ty - cy)
        guard = 0
        while accumulated < lookahead and guard < len(self.personal_path):
            nxt = (idx + 1) % len(self.personal_path)
            nx, ny = self.personal_path[nxt]
            seg = math.hypot(nx - tx, ny - ty)
            accumulated += seg
            idx = nxt
            tx, ty = nx, ny
            guard += 1

        diff = self._signed_angle_to(tx, ty)

        max_step = self.rotation_vel * (1.0 + min(0.34, abs(diff) / 360.0))
        rotate_amount = min(max_step, abs(diff))
        if abs(diff) < 1.5:
            rotate_amount *= 0.5

        if diff > 0:
            self.angle -= rotate_amount
        else:
            self.angle += rotate_amount

        return diff

    def _advance_passed_waypoints(self, total_laps):
        """Advance current_point when we're close enough or the WP is behind us."""
        cx, cy = self._car_center()

        radians = math.radians(self.angle)
        hx = -math.sin(radians)
        hy = -math.cos(radians)
        progressed = False

        for _ in range(len(self.personal_path)):
            tx, ty = self.personal_path[self.current_point]
            dx = tx - cx
            dy = ty - cy
            dist = math.hypot(dx, dy)

            within_radius = dist < 34
            behind = (dist < 86) and (dx * hx + dy * hy) < -8

            if not (within_radius or behind):
                break

            progressed = True
            if self._advance_one_waypoint(total_laps):
                return

        if not progressed:
            self._catch_missed_waypoints(total_laps, cx, cy, hx, hy)

    def _advance_one_waypoint(self, total_laps):
        self.current_point += 1
        self._points_since_lap_start += 1
        if self.current_point < len(self.personal_path):
            return False

        self.current_point = 0
        return False

    def _catch_missed_waypoints(self, total_laps, cx, cy, hx, hy):
        """Fast AI can skip a capture radius in hairpins; catch up to nearby future nodes."""
        tx, ty = self.personal_path[self.current_point]
        cur_dx = tx - cx
        cur_dy = ty - cy
        cur_dist = math.hypot(cur_dx, cur_dy)
        cur_ahead = cur_dx * hx + cur_dy * hy

        best_step = 0
        best_dist = cur_dist
        max_scan = min(120, len(self.personal_path) - self.current_point - 1)
        if max_scan <= 0:
            return
        for step in range(1, max_scan + 1):
            idx = (self.current_point + step) % len(self.personal_path)
            px, py = self.personal_path[idx]
            dist = math.hypot(px - cx, py - cy)
            if dist < best_dist:
                best_dist = dist
                best_step = step

        should_skip = (
            best_step > 0
            and (
                best_dist < 52
                or (cur_ahead < -18 and best_dist < cur_dist * 0.90)
                or (cur_dist > 170 and best_dist < cur_dist - 38)
            )
        )
        if not should_skip:
            return

        for _ in range(best_step):
            if self._advance_one_waypoint(total_laps):
                return

    def _move(self):
        radians = math.radians(self.angle)
        vertical = math.cos(radians) * self.vel
        horizontal = math.sin(radians) * self.vel
        old_x, old_y = self.x, self.y
        new_x = old_x - horizontal
        new_y = old_y - vertical

        self.x, self.y = new_x, new_y

    def _get_rotated(self, angle=None):
        if angle is None:
            angle = self.angle
        bucket = int(round(angle / self._mask_step)
                     * self._mask_step) % 360
        cached = self._rotated_cache.get(bucket)
        if cached is None:
            rotated = pygame.transform.rotate(self.img, bucket)
            mask = pygame.mask.from_surface(rotated)
            cached = (rotated, mask, rotated.get_size())
            self._rotated_cache[bucket] = cached
        return cached

    def check_collision(self, mask, x=0, y=0):
        rotated, car_mask, (mw, mh) = self._get_rotated()
        cx = self.x + self.img.get_width() / 2
        cy = self.y + self.img.get_height() / 2
        offset = (int(cx - mw / 2 - x), int(cy - mh / 2 - y))
        return mask.overlap(car_mask, offset)

    def _car_hits_border_at(self, x, y, angle=None):
        if self.border_mask is None:
            return False
        rotated, car_mask, (mw, mh) = self._get_rotated(angle)
        cx = x + self.img.get_width() / 2
        cy = y + self.img.get_height() / 2
        offset = (int(cx - mw / 2), int(cy - mh / 2))
        return self.border_mask.overlap(car_mask, offset) is not None

    def draw(self, win):
        rotated, _, (mw, mh) = self._get_rotated()
        cx = self.x + self.img.get_width() / 2
        cy = self.y + self.img.get_height() / 2
        sx, sy = track_to_screen(cx - mw / 2, cy - mh / 2)
        win.blit(rotated, (int(sx), int(sy)))
