"""AI competitor that follows a fixed racing path using pure pursuit."""
import math
import time

import pygame

class AIRacer:
    """Computer-controlled car that follows the racing path smoothly.

    Uses a "pure pursuit" steering model: instead of aiming straight at the
    next waypoint (which causes snaking when the waypoint is close or behind
    the car), it aims at a virtual point that sits a fixed distance further
    along the path. This is the same technique used by real autonomous
    vehicles and produces a much more natural racing line.
    """

    def __init__(self, name, image, max_vel, rotation_vel, path,
                 start_offset=0, lateral_offset=0, longitudinal_offset=0,
                 start_pos=None, accent_color=(200, 200, 200),
                 racing_line_offset=0, lookahead_bias=0,
                 border_mask=None, safety_margin=10,
                 apex_strength=1.0, corner_aggression=1.0,
                 accel_rate=0.07):
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
        self.personal_path = self._build_personal_path(racing_line_offset)

        self.vel = 0
        self.angle = 0
        self.current_point = start_offset % len(path)
        self.lap = 1
        self.finish_time = None
        self.race_start_time = None
        self.lap_times = []
        self._lap_start_time = None

        self._rotated_cache = {}
        self._mask_step = 6

        self._set_start_position()

    def _build_personal_path(self, bias_offset):
        """Build a real "out-in-out" racing line.

        Because the centre `path` is sparse (~20 waypoints), we first
        DENSIFY it by linear interpolation, compute the smoothed curvature
        on the dense version, then sample the offset back at each original
        waypoint. This gives a silky racing line that genuinely cuts the
        apex of every corner rather than averaging the whole track flat.
        """
        n = len(self.path)
        if n == 0:
            return []

        TARGET_DENSE = 240
        dense = []

        original_to_dense = [0] * n
        for i in range(n):
            a = self.path[i]
            b = self.path[(i + 1) % n]
            seg_len = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
            steps = max(1, int(round(TARGET_DENSE * seg_len /
                                      self._path_total_length())))
            original_to_dense[i] = len(dense)
            for k in range(steps):
                t = k / steps
                dense.append((a[0] + (b[0] - a[0]) * t,
                              a[1] + (b[1] - a[1]) * t))
        dn = len(dense)

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

        APEX_PIXELS = 26.0

        out = []
        for orig_i in range(n):
            di = original_to_dense[orig_i]
            curv_norm = smoothed[di] / max_curv
            apex_offset = curv_norm * APEX_PIXELS * self.apex_strength

            straight_factor = 1.0 - min(1.0, abs(curv_norm))
            target = apex_offset + bias_offset * straight_factor

            base_x, base_y = self.path[orig_i]

            px, py = perps[di]
            safe = self._clamp_offset(base_x, base_y, px, py, target)
            out.append((base_x + px * safe, base_y + py * safe))
        return out

    def _path_total_length(self):
        """Cached perimeter of the centre path."""
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

    def _point_inside_track(self, x, y):
        """Return True if a small bubble around (x,y) is fully inside the
        track corridor (no overlap with the border curb)."""
        if self.border_mask is None:
            return True
        ix, iy = int(x), int(y)
        r = max(1, int(self.safety_margin))

        samples = [(0, 0), (r, 0), (-r, 0), (0, r), (0, -r),
                   (r, r), (-r, -r), (r, -r), (-r, r)]
        mw, mh = self.border_mask.get_size()
        for dx, dy in samples:
            sx, sy = ix + dx, iy + dy
            if sx < 0 or sy < 0 or sx >= mw or sy >= mh:
                return False
            if self.border_mask.get_at((sx, sy)):
                return False
        return True

    def _clamp_offset(self, base_x, base_y, px, py, requested):
        """Pull `requested` toward 0 in 1-px steps until the resulting
        point is safely inside the track."""
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

            tx, ty = self.personal_path[self.current_point]
            x_diff = tx - sx
            y_diff = ty - sy
        else:
            sx, sy = self.personal_path[self.start_offset]
            nx, ny = self.personal_path[
                (self.start_offset + 1) % len(self.personal_path)]
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

        self.x = sx - self.img.get_width() / 2
        self.y = sy - self.img.get_height() / 2

    def reset(self):
        self.vel = 0
        self.lap = 1
        self.current_point = (self.start_offset + 1) % len(self.path)
        self.finish_time = None
        self.race_start_time = None
        self.lap_times = []
        self._lap_start_time = None
        self._set_start_position()

    def start(self, race_start_time):
        self.race_start_time = race_start_time
        self._lap_start_time = race_start_time
        self.vel = 0

    def progress_score(self):
        """Higher = further along in the race."""
        return self.lap * len(self.path) + self.current_point

    def update(self, total_laps):
        if self.finish_time is not None:
            return
        if self.race_start_time is None:
            return

        self._advance_passed_waypoints(total_laps)

        steer_diff = self._steer_towards_lookahead()

        turn_lift = abs(steer_diff) / (85.0 * self.corner_aggression)
        turn_factor = max(0.55, 1.0 - turn_lift)
        target_vel = self.max_vel * turn_factor

        if self._near_border():
            target_vel *= 0.55
            self._nudge_back_to_path()

        if self.vel < target_vel:
            self.vel = min(self.vel + self.accel_rate, target_vel)
        else:
            self.vel = max(self.vel - 0.18, target_vel)

        self._move()

    def _near_border(self):
        """True if the car's current centre is within safety_margin of the
        track curb (i.e. about to clip or already clipping)."""
        if self.border_mask is None:
            return False
        cx, cy = self._car_center()
        return not self._point_inside_track(cx, cy)

    def _nudge_back_to_path(self):
        """Apply an immediate steering correction toward the centre line
        when we're brushing the curb. This guarantees we never get stuck
        on/outside the wall."""
        cx, cy = self._car_center()

        tx, ty = self.path[self.current_point]
        diff = self._signed_angle_to(tx, ty)

        step = min(self.rotation_vel * 2.0, abs(diff))
        if diff > 0:
            self.angle -= step
        else:
            self.angle += step

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
        """Find a virtual target ~lookahead px ahead and steer toward it."""
        cx, cy = self._car_center()

        lookahead = 38 + self.vel * 6 + self.lookahead_bias
        lookahead = max(28, lookahead)

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

        max_step = self.rotation_vel
        rotate_amount = min(max_step, abs(diff))
        if abs(diff) < 1.5:
            rotate_amount *= 0.5

        if diff > 0:
            self.angle -= rotate_amount
        else:
            self.angle += rotate_amount

        return diff

    def _advance_passed_waypoints(self, total_laps):
        """Skip waypoints that the car has already driven past.

        A waypoint counts as "passed" if it's within the capture radius
        OR if it lies behind the car (negative dot product with heading).
        """
        cx, cy = self._car_center()

        radians = math.radians(self.angle)
        hx = -math.sin(radians)
        hy = -math.cos(radians)

        for _ in range(len(self.personal_path)):
            tx, ty = self.personal_path[self.current_point]
            dx = tx - cx
            dy = ty - cy
            dist = math.hypot(dx, dy)

            within_radius = dist < 40

            behind = (dist < 90) and (dx * hx + dy * hy) < 0

            if not (within_radius or behind):
                break

            self.current_point += 1
            if self.current_point >= len(self.personal_path):
                self.current_point = 0

                now = time.time()
                if self._lap_start_time is not None:
                    lap_time = now - self._lap_start_time
                    self.lap_times.append(round(lap_time, 3))
                    self._lap_start_time = now
                self.lap += 1
                if self.lap > total_laps:
                    self.finish_time = now - self.race_start_time
                    self.vel = 0
                    return

    def _move(self):
        radians = math.radians(self.angle)
        vertical = math.cos(radians) * self.vel
        horizontal = math.sin(radians) * self.vel
        self.y -= vertical
        self.x -= horizontal

    def _get_rotated(self):
        bucket = int(round(self.angle / self._mask_step)
                     * self._mask_step) % 360
        cached = self._rotated_cache.get(bucket)
        if cached is None:
            rotated = pygame.transform.rotate(self.img, bucket)
            cached = (rotated, rotated.get_size())
            self._rotated_cache[bucket] = cached
        return cached

    def draw(self, win):
        rotated, (mw, mh) = self._get_rotated()
        cx = self.x + self.img.get_width() / 2
        cy = self.y + self.img.get_height() / 2
        win.blit(rotated, (cx - mw / 2, cy - mh / 2))
