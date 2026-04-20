"""Player and base car physics."""
import math

import pygame

from assets import RED_CAR
from settings import _PATH_SCALE

_CAR_SHADOW_CACHE = {}


def get_car_shadow(width, height):
    """Soft elliptical drop-shadow rendered once per size."""
    key = (width, height)
    cached = _CAR_SHADOW_CACHE.get(key)
    if cached is not None:
        return cached
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    layers = 5
    for i in range(layers, 0, -1):
        alpha = int(45 * (i / layers))
        rect = pygame.Rect(
            int((1 - i / layers) * width * 0.35 / 2),
            int((1 - i / layers) * height * 0.35 / 2),
            width - int((1 - i / layers) * width * 0.35),
            height - int((1 - i / layers) * height * 0.35),
        )
        pygame.draw.ellipse(surf, (0, 0, 0, alpha), rect)
    _CAR_SHADOW_CACHE[key] = surf
    return surf


class Car:
    """Base car physics: speed, acceleration, rotation."""

    IMG = None
    START_POS = (0, 0)
    _ROTATED_CACHE = {}
    MASK_ANGLE_STEP = 3

    def __init__(self, max_vel, rotation_vel, image=None, start_pos=None):
        self.img = image if image is not None else self.IMG
        self.max_vel = max_vel
        self.base_max_vel = max_vel
        self.vel = 0
        self.rotation_vel = rotation_vel
        self.angle = 0
        start = start_pos if start_pos is not None else self.START_POS
        self.start_pos = start
        self.x, self.y = start
        self.acceleration = 0.1
        self._last_safe_pos = start

    def rotate(self, left=False, right=False):
        speed_factor = max(0.55, 1.0 - abs(self.vel) / (self.max_vel * 2.5))
        amount = self.rotation_vel * speed_factor
        if left:
            self.angle += amount
        elif right:
            self.angle -= amount

    def draw(self, win):
        rotated, _, (mw, mh) = self._get_rotated()
        cx = self.x + self.img.get_width() / 2
        cy = self.y + self.img.get_height() / 2

        shadow_w = int(self.img.get_width() * 0.95)
        shadow_h = max(8, int(self.img.get_height() * 0.32))
        shadow = get_car_shadow(shadow_w, shadow_h)
        win.blit(shadow, (cx - shadow_w / 2 + 4,
                          cy - shadow_h / 2 + 8))
        win.blit(rotated, (cx - mw / 2, cy - mh / 2))

    def drive(self, forward=False, backward=False):
        """Single entry point for driving (PDF: Car.drive())."""
        if forward:
            self.vel = min(self.vel + self.acceleration, self.max_vel)
            self._move()
        elif backward:
            self.vel = max(self.vel - self.acceleration, -self.max_vel / 2)
            self._move()

    def apply_friction(self):
        """Coast to a stop when no input (PDF: Car.applyFriction())."""
        if self.vel > 0:
            self.vel = max(self.vel - self.acceleration / 2, 0)
        elif self.vel < 0:
            self.vel = min(self.vel + self.acceleration / 2, 0)
        self._move()

    def _move(self):
        radians = math.radians(self.angle)
        vertical = math.cos(radians) * self.vel
        horizontal = math.sin(radians) * self.vel
        self.y -= vertical
        self.x -= horizontal

    def _get_rotated(self):
        """Return (rotated_image, mask, size) for current angle, cached."""
        bucket = int(round(self.angle / self.MASK_ANGLE_STEP)
                     * self.MASK_ANGLE_STEP) % 360
        key = (id(self.img), bucket)
        cached = Car._ROTATED_CACHE.get(key)
        if cached is None:
            rotated = pygame.transform.rotate(self.img, bucket)
            mask = pygame.mask.from_surface(rotated)
            cached = (rotated, mask, rotated.get_size())
            Car._ROTATED_CACHE[key] = cached
        return cached

    def check_collision(self, mask, x=0, y=0):
        """Mask-based collision using a rotated mask aligned with the car's
        actual on-screen orientation."""
        _, car_mask, (mw, mh) = self._get_rotated()
        cx = self.x + self.img.get_width() / 2
        cy = self.y + self.img.get_height() / 2
        offset = (int(cx - mw / 2 - x), int(cy - mh / 2 - y))
        return mask.overlap(car_mask, offset)

    @property
    def rect(self):
        w, h = self.img.get_width(), self.img.get_height()
        return pygame.Rect(self.x, self.y, w, h)

    def reset(self):
        self.x, self.y = self.start_pos
        self.angle = 0
        self.vel = 0
        self._last_safe_pos = self.start_pos


class PlayerCar(Car):
    IMG = RED_CAR
    START_POS = (int(180 * _PATH_SCALE), int(200 * _PATH_SCALE))
    NITRO_MULTIPLIER = 1.6

    def __init__(self, max_vel, rotation_vel):
        super().__init__(max_vel, rotation_vel)
        self.nitro_charge = 0.0
        self.nitro_active = False
        self.nitro_max = 5.0

    def add_nitro(self, seconds):
        self.nitro_charge = min(self.nitro_charge + seconds, self.nitro_max)

    def update_nitro(self, dt, requested):
        """Activate nitro while requested and charge remains."""
        if requested and self.nitro_charge > 0:
            self.nitro_active = True
            self.nitro_charge = max(0.0, self.nitro_charge - dt)
            self.max_vel = self.base_max_vel * self.NITRO_MULTIPLIER
        else:
            self.nitro_active = False
            self.max_vel = self.base_max_vel
        if self.nitro_charge <= 0:
            self.nitro_active = False

    _ESCAPE_DIRECTIONS = [
        (math.cos(math.radians(a)), math.sin(math.radians(a)))
        for a in range(0, 360, 30)
    ]

    def bounce_off_wall(self, track):
        """Wall-slide physics: find the shortest direction out of the wall
        (= wall normal), push the car there, then project velocity onto the
        wall tangent so the car keeps moving smoothly along the wall instead
        of stuttering back-and-forth into it."""
        saved_x, saved_y = self.x, self.y
        best_normal = None
        best_dist = None

        for dx, dy in self._ESCAPE_DIRECTIONS:
            for d in range(1, 25):
                self.x = saved_x + dx * d
                self.y = saved_y + dy * d
                if not track.is_out_of_bounds(self):
                    if best_dist is None or d < best_dist:
                        best_dist = d
                        best_normal = (dx, dy)
                    break

        self.x = saved_x
        self.y = saved_y

        if best_normal is None:
            if self._last_safe_pos is not None:
                self.x, self.y = self._last_safe_pos
            self.vel *= 0.3
            return

        nx, ny = best_normal
        self.x = saved_x + nx * (best_dist + 0.5)
        self.y = saved_y + ny * (best_dist + 0.5)

        radians = math.radians(self.angle)
        sin_a = math.sin(radians)
        cos_a = math.cos(radians)
        vx = -sin_a * self.vel
        vy = -cos_a * self.vel

        dot = vx * nx + vy * ny
        if dot < 0:
            vx -= dot * nx
            vy -= dot * ny

        new_speed = vx * (-sin_a) + vy * (-cos_a)
        self.vel = new_speed * 0.9

    def reset(self):
        super().reset()
        self.nitro_charge = 0.0
        self.nitro_active = False
        self.max_vel = self.base_max_vel
