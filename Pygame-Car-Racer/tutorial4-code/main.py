"""Formula 67 - Arcade Racing Game.

Implements the project proposal:
  * Classes: Car, Track, RaceManager, Obstacle, StatsLogger (+ Leaderboard)
  * 3-lap time trial with obstacles + nitro boost pads
  * AABB collision for obstacles, mask collision for track borders
  * 5 statistical features logged to CSV (>=100 records achievable)
  * Top-10 leaderboard with insertion sort
"""
import math
import os
import random
import time

import pygame

from utils import (
    scale_image,
    blit_rotate_center,
    blit_text_center,
    render_text_with_shadow,
    draw_rounded_panel,
    draw_progress_bar,
    draw_vignette,
)
from track import Track
from obstacle import NitroPad, spawn_obstacles
from race import RaceManager
from stats import StatsLogger, Leaderboard
from ai_racer import AIRacer
try:
    from visualize import generate_report
except ImportError:
    generate_report = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def asset_path(*parts):
    """Return an absolute path to a bundled asset (cross-platform safe)."""
    return os.path.join(BASE_DIR, *parts)

pygame.font.init()

TRACK_SCALE = 0.95
_BASE_SCALE = 0.9
_PATH_SCALE = TRACK_SCALE / _BASE_SCALE

GRASS = scale_image(pygame.image.load(asset_path("imgs", "grass.png")),
                    2.5 * _PATH_SCALE)
TRACK_SURFACE = scale_image(pygame.image.load(asset_path("imgs", "track.png")),
                            TRACK_SCALE)
TRACK_BORDER = scale_image(
    pygame.image.load(asset_path("imgs", "track-border.png")),
    TRACK_SCALE,
)
TRACK_BORDER_MASK = pygame.mask.from_surface(TRACK_BORDER)

FINISH = pygame.image.load(asset_path("imgs", "finish.png"))
FINISH_POSITION = (int(130 * _PATH_SCALE), int(250 * _PATH_SCALE))

RED_CAR = scale_image(pygame.image.load(asset_path("imgs", "red-car.png")),
                      0.55)
GREEN_CAR = scale_image(pygame.image.load(asset_path("imgs", "green-car.png")),
                        0.55)
PURPLE_CAR = scale_image(
    pygame.image.load(asset_path("imgs", "purple-car.png")), 0.55)
WHITE_CAR = scale_image(pygame.image.load(asset_path("imgs", "white-car.png")),
                        0.55)

WIDTH, HEIGHT = TRACK_SURFACE.get_width(), TRACK_SURFACE.get_height()

def _create_window(width, height):
    """Open the game window. Try fullscreen first, then fall back to a
    plain window if the OS/driver refuses the requested mode (this can
    happen on some Windows GPU setups, remote desktops, or virtual
    machines where SCALED|FULLSCREEN is unsupported)."""
    try:
        return pygame.display.set_mode(
            (width, height), pygame.SCALED | pygame.FULLSCREEN
        )
    except pygame.error:
        try:
            return pygame.display.set_mode(
                (width, height), pygame.SCALED
            )
        except pygame.error:
            return pygame.display.set_mode((width, height))

WIN = _create_window(WIDTH, HEIGHT)
pygame.display.set_caption("Formula 67 - Arcade Racing")

MAIN_FONT = pygame.font.SysFont("comicsans", 44)
TITLE_FONT = pygame.font.SysFont("comicsans", 56, bold=True)
HUD_FONT = pygame.font.SysFont("comicsans", 22, bold=True)
HUD_FONT_SMALL = pygame.font.SysFont("comicsans", 16)

FPS = 60

KMH_FACTOR = 36
SPEEDO_MAX_KMH = 280

_HUD_LABEL_CACHE = {}
_MINIMAP_PATH_SURFACE = None
_FLAME_SPRITES = []
_SPEEDO_BASE = None
_SPEEDO_DIGIT_FONT = None
_CAR_SHADOW_CACHE = {}

def _get_car_shadow(width, height):
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

def _get_speedo_digit_font():
    global _SPEEDO_DIGIT_FONT
    if _SPEEDO_DIGIT_FONT is None:
        _SPEEDO_DIGIT_FONT = pygame.font.SysFont("comicsans", 24, bold=True)
    return _SPEEDO_DIGIT_FONT

_MENU_OVERLAY = None
_RESULTS_OVERLAY = None
_MENU_STATIC_CACHE = None
_MENU_LEADERBOARD_CACHE = None
_MENU_BG_SNAPSHOT = None
_RESULTS_BG_SNAPSHOT = None
_RESULTS_PANEL_CACHE = None
_DIFFICULTY_PICKER_CACHE = None
_START_BTN_CACHE = None
_COUNTDOWN_BG_SNAPSHOT = None

_DIFFICULTY_CARD_RECTS = {}
_START_BUTTON_RECT = None

DIFFICULTIES = {
    "EASY": {
        "label": "EASY",
        "color": (110, 220, 140),
        "icon": "shield",
        "ai_speed_mult": 0.78,
        "ai_lookahead_bonus": -6,
        "ai_rotation_mult": 0.88,
        "ai_apex_strength": 0.30,
        "ai_corner_aggression": 0.78,
        "ai_accel_rate": 0.04,
        "obstacles": 0,
        "nitro_max": 9.0,
        "desc": "Cruise to the win",
    },
    "MEDIUM": {
        "label": "MEDIUM",
        "color": (255, 215, 100),
        "icon": "bolt",
        "ai_speed_mult": 0.86,
        "ai_lookahead_bonus": -4,
        "ai_rotation_mult": 0.94,
        "ai_apex_strength": 0.45,
        "ai_corner_aggression": 0.85,
        "ai_accel_rate": 0.05,
        "obstacles": 1,
        "nitro_max": 7.0,
        "desc": "A balanced challenge",
    },
    "HARD": {
        "label": "HARD",
        "color": (240, 90, 110),
        "icon": "skull",
        "ai_speed_mult": 1.0,
        "ai_lookahead_bonus": 14,
        "ai_rotation_mult": 1.55,
        "ai_apex_strength": 1.0,
        "ai_corner_aggression": 1.30,
        "ai_accel_rate": 0.10,
        "obstacles": 6,
        "nitro_max": 1.5,
        "desc": "Optimal apex line - relentless",
    },
}
DIFFICULTY_ORDER = ["EASY", "MEDIUM", "HARD"]

def _player_progress_score(player_car, race_manager, path):
    """Estimate the player's progress as lap*len(path) + nearest_path_index."""
    px = player_car.x + player_car.img.get_width() / 2
    py = player_car.y + player_car.img.get_height() / 2
    best_i = 0
    best_d = float("inf")
    for i, (qx, qy) in enumerate(path):
        d = (px - qx) ** 2 + (py - qy) ** 2
        if d < best_d:
            best_d = d
            best_i = i
    lap = max(1, race_manager.current_lap)
    return lap * len(path) + best_i

def compute_standings(player_car, ai_racers, race_manager, path,
                      race_finished=False):
    """Return a sorted list of dicts: [{'name','is_player','finish_time',
    'lap','progress','color'}, ...] best first."""
    entries = []
    if race_finished and race_manager.lap_times:
        player_finish = sum(race_manager.lap_times)
    else:
        player_finish = None
    player_best = (min(race_manager.lap_times)
                   if race_manager.lap_times else None)
    entries.append({
        "name": "You",
        "is_player": True,
        "finish_time": player_finish,
        "lap": race_manager.current_lap,
        "progress": _player_progress_score(player_car, race_manager, path),
        "color": (255, 90, 90),
        "best_lap": player_best,
    })
    for ai in ai_racers:
        entries.append({
            "name": ai.name,
            "is_player": False,
            "finish_time": ai.finish_time,
            "lap": ai.lap,
            "progress": ai.progress_score(),
            "color": ai.accent_color,
            "best_lap": ai.best_lap_time(),
        })

    def sort_key(e):
        if e["finish_time"] is not None:
            return (0, e["finish_time"])
        return (1, -e["progress"])
    entries.sort(key=sort_key)
    for i, e in enumerate(entries, start=1):
        e["rank"] = i
    return entries

def _get_label(text, color=(170, 200, 230)):
    key = (text, color)
    cached = _HUD_LABEL_CACHE.get(key)
    if cached is None:
        cached = HUD_FONT_SMALL.render(text, True, color)
        _HUD_LABEL_CACHE[key] = cached
    return cached

_BASE_PATH = [(175, 119), (110, 70), (56, 133), (70, 481), (318, 731),
              (404, 680), (418, 521), (507, 475), (600, 551), (613, 715),
              (736, 713), (734, 399), (611, 357), (409, 343), (433, 257),
              (697, 258), (738, 123), (581, 71), (303, 78), (275, 377),
              (176, 388), (178, 260)]
PATH = [(int(x * _PATH_SCALE), int(y * _PATH_SCALE)) for x, y in _BASE_PATH]

_BASE_NITRO_PADS = [(70, 300), (320, 700), (650, 600), (700, 200)]
NITRO_PAD_POSITIONS = [(int(x * _PATH_SCALE), int(y * _PATH_SCALE))
                       for x, y in _BASE_NITRO_PADS]


# ---------------------------------------------------------------------------
# Car physics (base + player subclass)
# ---------------------------------------------------------------------------
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
        shadow = _get_car_shadow(shadow_w, shadow_h)
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


# ---------------------------------------------------------------------------
# HUD: speedometer, mini-map, standings panel
# ---------------------------------------------------------------------------
def draw_hud(win, player_car, race_manager, standings=None):

    panel_w, panel_h = 320, 86
    margin = 14
    panel_rect = pygame.Rect(margin, margin, panel_w, panel_h)

    draw_rounded_panel(win, panel_rect,
                       fill=(10, 14, 28, 215),
                       border=(120, 220, 255, 220),
                       radius=14, width=2)

    value_color = (245, 250, 255)
    accent = (255, 215, 100)

    win.blit(_get_label("LAP"), (panel_rect.x + 16, panel_rect.y + 8))
    lap_value = HUD_FONT.render(
        f"{max(1, race_manager.current_lap)}/{race_manager.TOTAL_LAPS}",
        True, accent)
    win.blit(lap_value, (panel_rect.x + 16, panel_rect.y + 24))

    win.blit(_get_label("TIME"), (panel_rect.x + 88, panel_rect.y + 8))
    time_value = HUD_FONT.render(
        f"{race_manager.get_race_time():.1f}s", True, value_color)
    win.blit(time_value, (panel_rect.x + 88, panel_rect.y + 24))

    win.blit(_get_label("HITS"), (panel_rect.x + 188, panel_rect.y + 8))
    hits_value = HUD_FONT.render(
        f"{race_manager.collision_count}", True, (255, 130, 130))
    win.blit(hits_value, (panel_rect.x + 188, panel_rect.y + 24))

    if standings:
        player_rank = next((s["rank"] for s in standings
                            if s["is_player"]), 1)
        win.blit(_get_label("POS"), (panel_rect.x + 248, panel_rect.y + 8))
        pos_color = (255, 215, 100) if player_rank == 1 else value_color
        pos_value = HUD_FONT.render(
            f"{player_rank}/{len(standings)}", True, pos_color)
        win.blit(pos_value, (panel_rect.x + 248, panel_rect.y + 24))

    win.blit(_get_label("NITRO"), (panel_rect.x + 16, panel_rect.y + 52))
    nitro_bar = pygame.Rect(panel_rect.x + 64, panel_rect.y + 56,
                            panel_w - 84, 10)
    nitro_fg = (255, 180, 80) if player_car.nitro_active else (255, 120, 60)
    draw_progress_bar(win, nitro_bar,
                      value=player_car.nitro_charge,
                      max_value=player_car.nitro_max,
                      fg=nitro_fg, bg=(30, 40, 60),
                      border=(255, 200, 140), radius=5)
    nitro_text = HUD_FONT_SMALL.render(
        f"{player_car.nitro_charge:.1f}s [SHIFT]", True, value_color)
    win.blit(nitro_text,
             (panel_rect.right - nitro_text.get_width() - 14,
              panel_rect.y + 70))

def _gauge_xy(cx, cy, radius, t):
    """Map t in [0,1] to a point on a 270-degree arc gauge.

    t=0  -> lower-left  (7-o'clock)
    t=0.5-> top         (12-o'clock)
    t=1  -> lower-right (5-o'clock)
    """
    angle_from_top_cw = -135 + 270 * t
    rad = math.radians(90 - angle_from_top_cw)
    return (cx + radius * math.cos(rad),
            cy - radius * math.sin(rad))

def _build_speedometer_base(size=130, max_kmh=SPEEDO_MAX_KMH):
    """Pre-render the static speedometer dial (background, ticks, labels)."""
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = cy = size // 2
    radius = size // 2 - 6

    pygame.draw.circle(surf, (8, 12, 24, 235), (cx, cy), radius + 4)
    pygame.draw.circle(surf, (40, 60, 90, 255), (cx, cy), radius + 4, 3)
    pygame.draw.circle(surf, (180, 220, 255, 230), (cx, cy), radius + 1, 1)

    for i in range(6):
        alpha = 60 - i * 8
        if alpha <= 0:
            continue
        pygame.draw.circle(
            surf, (120, 200, 255, alpha), (cx, cy), radius - 2 - i, 1
        )

    arc_outer_r = radius - 4
    arc_inner_r = radius - 10
    steps = 90
    for i in range(steps):
        t0 = i / steps
        t1 = (i + 1) / steps

        if t0 < 0.55:
            color = (90, 220, 130)
        elif t0 < 0.8:
            color = (240, 210, 90)
        else:
            color = (240, 90, 90)
        x0o, y0o = _gauge_xy(cx, cy, arc_outer_r, t0)
        x1o, y1o = _gauge_xy(cx, cy, arc_outer_r, t1)
        x0i, y0i = _gauge_xy(cx, cy, arc_inner_r, t0)
        x1i, y1i = _gauge_xy(cx, cy, arc_inner_r, t1)
        pygame.draw.polygon(
            surf, color,
            [(x0o, y0o), (x1o, y1o), (x1i, y1i), (x0i, y0i)],
        )

    label_font = pygame.font.SysFont("comicsans", 12, bold=True)
    n_major = 7
    for i in range(n_major):
        t = i / (n_major - 1)
        kmh_val = int(round(t * max_kmh / 10) * 10)
        x_outer, y_outer = _gauge_xy(cx, cy, radius - 4, t)
        x_inner, y_inner = _gauge_xy(cx, cy, radius - 18, t)
        pygame.draw.line(
            surf, (230, 240, 255), (x_outer, y_outer), (x_inner, y_inner), 2
        )

        lx, ly = _gauge_xy(cx, cy, radius - 30, t)
        lbl = label_font.render(str(kmh_val), True, (210, 230, 250))
        surf.blit(lbl, (lx - lbl.get_width() / 2,
                        ly - lbl.get_height() / 2))

    for i in range(31):
        t = i / 30

        nearest_major = round(t * (n_major - 1)) / (n_major - 1)
        if abs(t - nearest_major) < 0.02:
            continue
        x_outer, y_outer = _gauge_xy(cx, cy, radius - 4, t)
        x_inner, y_inner = _gauge_xy(cx, cy, radius - 12, t)
        pygame.draw.line(
            surf, (160, 180, 210), (x_outer, y_outer), (x_inner, y_inner), 1
        )

    unit_font = pygame.font.SysFont("comicsans", 10, bold=True)
    unit_lbl = unit_font.render("KM/H", True, (180, 210, 240))
    surf.blit(unit_lbl, (cx - unit_lbl.get_width() / 2, cy + radius - 22))

    return {"surf": surf, "size": size, "cx": cx, "cy": cy,
            "radius": radius, "max_kmh": max_kmh}

def draw_speedometer(win, kmh, nitro_active=False):
    """Draw a circular speedometer at the bottom-center of the screen."""
    global _SPEEDO_BASE
    if _SPEEDO_BASE is None:
        _SPEEDO_BASE = _build_speedometer_base()

    base = _SPEEDO_BASE
    size = base["size"]
    margin = 14

    px = margin
    py = HEIGHT - size - margin

    win.blit(base["surf"], (px, py))

    cx = px + base["cx"]
    cy = py + base["cy"]
    radius = base["radius"]

    t = max(0.0, min(1.0, kmh / base["max_kmh"]))
    nx, ny = _gauge_xy(cx, cy, radius - 12, t)
    bx, by = _gauge_xy(cx, cy, -8, t)

    needle_color = (255, 90, 90) if nitro_active else (255, 220, 110)
    pygame.draw.line(win, (0, 0, 0), (bx, by), (nx, ny), 4)
    pygame.draw.line(win, needle_color, (bx, by), (nx, ny), 2)
    pygame.draw.circle(win, (30, 30, 40), (cx, cy), 7)
    pygame.draw.circle(win, needle_color, (cx, cy), 5)
    pygame.draw.circle(win, (10, 10, 14), (cx, cy), 2)

    digit_font = _get_speedo_digit_font()
    digital = digit_font.render(f"{int(kmh)}", True, (255, 255, 255))
    shadow = digit_font.render(f"{int(kmh)}", True, (0, 0, 0))
    dx = cx - digital.get_width() // 2
    dy = cy + radius - 50
    win.blit(shadow, (dx + 2, dy + 2))
    win.blit(digital, (dx, dy))

    if nitro_active:
        boost_lbl = HUD_FONT_SMALL.render("NITRO", True, (255, 130, 80))
        win.blit(boost_lbl,
                 (cx - boost_lbl.get_width() // 2, py + 6))

def _build_minimap_base():
    """Pre-render the static parts of the minimap once (panel + path)."""
    global _MINIMAP_PATH_SURFACE
    mm_w, mm_h = 140, 140
    surf = pygame.Surface((mm_w, mm_h), pygame.SRCALPHA)
    panel_rect = pygame.Rect(0, 0, mm_w, mm_h)
    draw_rounded_panel(surf, panel_rect,
                       fill=(10, 14, 28, 200),
                       border=(120, 220, 255, 200),
                       radius=12, width=2)
    inner = panel_rect.inflate(-12, -12)
    sx = inner.width / WIDTH
    sy = inner.height / HEIGHT
    pygame.draw.lines(
        surf, (90, 110, 140), True,
        [(inner.x + p[0] * sx, inner.y + p[1] * sy) for p in PATH], 1,
    )
    surf.blit(_get_label("MAP"), (8, 4))
    _MINIMAP_PATH_SURFACE = (surf, inner, sx, sy)
    return _MINIMAP_PATH_SURFACE

def draw_minimap(win, player_car, obstacles, nitro_pads, ai_racers=()):
    base = _MINIMAP_PATH_SURFACE or _build_minimap_base()
    surf, inner, sx, sy = base
    mm_w = surf.get_width()
    margin = 14
    mm_x = WIDTH - mm_w - margin
    mm_y = margin
    win.blit(surf, (mm_x, mm_y))

    for ob in obstacles:
        if not ob.active:
            continue
        ox = mm_x + inner.x + ob.position[0] * sx
        oy = mm_y + inner.y + ob.position[1] * sy
        pygame.draw.circle(win, (255, 140, 30), (int(ox), int(oy)), 2)

    for pad in nitro_pads:
        nx = mm_x + inner.x + pad.position[0] * sx
        ny = mm_y + inner.y + pad.position[1] * sy
        color = (90, 220, 255) if pad.cooldown <= 0 else (90, 100, 130)
        pygame.draw.circle(win, color, (int(nx), int(ny)), 3)

    for ai in ai_racers:
        ax = mm_x + inner.x + ai.x * sx
        ay = mm_y + inner.y + ai.y * sy
        pygame.draw.circle(win, ai.accent_color, (int(ax), int(ay)), 3)

    px = mm_x + inner.x + player_car.x * sx
    py = mm_y + inner.y + player_car.y * sy
    pygame.draw.circle(win, (255, 90, 90), (int(px), int(py)), 4)

def draw_standings_panel(win, standings):
    if not standings:
        return
    panel_w = 180
    row_h = 20
    panel_h = 26 + row_h * len(standings)
    margin = 14

    minimap_h = 140
    panel_rect = pygame.Rect(WIDTH - panel_w - margin,
                             margin + minimap_h + 8,
                             panel_w, panel_h)
    draw_rounded_panel(win, panel_rect,
                       fill=(10, 14, 28, 210),
                       border=(255, 215, 100, 180),
                       radius=12, width=2)
    win.blit(_get_label("STANDINGS", color=(255, 215, 100)),
             (panel_rect.x + 12, panel_rect.y + 8))
    for i, s in enumerate(standings):
        y = panel_rect.y + 28 + i * row_h
        rank_color = (255, 215, 100) if s["is_player"] else (200, 220, 240)
        pygame.draw.circle(win, s["color"],
                           (panel_rect.x + 16, y + 8), 5)
        text = f"{s['rank']}. {s['name'][:10]:<10}  L{s['lap']}"
        surf = HUD_FONT_SMALL.render(text, True, rank_color)
        win.blit(surf, (panel_rect.x + 28, y))


# ---------------------------------------------------------------------------
# World rendering + per-frame input/collision handling
# ---------------------------------------------------------------------------
def draw_world(win, track, obstacles, nitro_pads, player_car, ai_racers,
               race_manager, standings=None, show_overlays=True):
    win.blit(GRASS, (0, 0))
    track.draw(win)

    for pad in nitro_pads:
        pad.render(win)
    for ob in obstacles:
        ob.render(win)

    for ai in ai_racers:
        ai.draw(win)
    player_car.draw(win)

    if player_car.nitro_active:
        if not _FLAME_SPRITES:
            for i in range(3):
                alpha = 200 - i * 60
                flame = pygame.Surface((10, 10), pygame.SRCALPHA)
                pygame.draw.circle(flame, (255, 140, 40, alpha),
                                   (5, 5), 5 - i)
                _FLAME_SPRITES.append(flame)
        radians = math.radians(player_car.angle)
        sin_a = math.sin(radians)
        cos_a = math.cos(radians)
        cx = player_car.x + player_car.img.get_width() / 2
        cy = player_car.y + player_car.img.get_height() / 2
        for i, flame in enumerate(_FLAME_SPRITES):
            offset = (i + 1) * 8
            fx = cx + sin_a * offset
            fy = cy + cos_a * offset
            win.blit(flame, (fx - 5, fy - 5))

    draw_vignette(win)
    if show_overlays:
        draw_hud(win, player_car, race_manager, standings)
        draw_minimap(win, player_car, obstacles, nitro_pads, ai_racers)
        draw_standings_panel(win, standings)
        draw_speedometer(win,
                         abs(player_car.vel) * KMH_FACTOR,
                         nitro_active=player_car.nitro_active)
    pygame.display.update()

def handle_input(player_car, race_manager, keys, stats_logger=None):
    moved = False
    if keys[pygame.K_a] or keys[pygame.K_LEFT]:
        player_car.rotate(left=True)
        race_manager.register_steering("left")
        if stats_logger is not None:
            stats_logger.log_steering_event("left")
    if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
        player_car.rotate(right=True)
        race_manager.register_steering("right")
        if stats_logger is not None:
            stats_logger.log_steering_event("right")
    if keys[pygame.K_w] or keys[pygame.K_UP]:
        moved = True
        player_car.drive(forward=True)
    if keys[pygame.K_s] or keys[pygame.K_DOWN]:
        moved = True
        player_car.drive(backward=True)
    if not moved:
        player_car.apply_friction()

def handle_obstacles_and_nitro(player_car, obstacles, nitro_pads,
                               race_manager, dt, stats_logger=None):
    car_rect = player_car.rect
    for ob in obstacles:
        if ob.update_collision(car_rect):
            if ob.on_hit(player_car):
                race_manager.register_collision()
                if stats_logger is not None:
                    stats_logger.log_collision_event(
                        race_manager.current_lap, source="obstacle")
    for pad in nitro_pads:
        pad.update()
        if pad.aabb_collides_with(car_rect):
            pad.on_hit(player_car)
    if player_car.nitro_active:
        race_manager.add_nitro_time(dt)

    burst_ended, burst_dur, burst_avg = race_manager.track_nitro_burst(
        player_car.nitro_active, player_car.vel)
    if burst_ended and stats_logger is not None:
        stats_logger.log_nitro_event(
            race_manager.current_lap, burst_dur, burst_avg)

def handle_track_collision(player_car, track, race_manager, finish_state,
                           stats_logger=None):
    """Wall collision + finish-line lap counting. Returns updated state."""
    if track.is_out_of_bounds(player_car):
        was_safe = getattr(player_car, "_was_on_track", True)
        player_car.bounce_off_wall(track)
        player_car._was_on_track = False
        if was_safe and stats_logger is not None:
            stats_logger.log_collision_event(
                race_manager.current_lap, source="wall")
    else:
        player_car._last_safe_pos = (player_car.x, player_car.y)
        player_car._was_on_track = True

    finish_collision = track.at_finish_line(player_car)
    on_finish = finish_collision is not None

    if on_finish and not finish_state["was_on"]:
        if finish_collision[1] != 0:
            done = race_manager.track_lap_time()
            finish_state["just_finished"] = done

    finish_state["was_on"] = on_finish
    return finish_state


# ---------------------------------------------------------------------------
# Start screen: menu, difficulty picker, leaderboard panel
# ---------------------------------------------------------------------------
def _build_menu_static():
    """Build text surfaces that never change while on the menu."""
    title = render_text_with_shadow(
        TITLE_FONT, "FORMULA 67",
        color=(255, 220, 110), shadow_color=(0, 0, 0), offset=4)
    subtitle = HUD_FONT.render(
        "3-Lap Time Trial", True, (200, 220, 255))
    hint = HUD_FONT_SMALL.render(
        "W/S = drive   A/D = steer   SHIFT = nitro   "
        "F11 = fullscreen   ESC = quit",
        True, (180, 200, 230))
    diff_hint = HUD_FONT_SMALL.render(
        "Click a card or press 1 / 2 / 3 to choose difficulty",
        True, (200, 220, 240))
    header = HUD_FONT.render("LEADERBOARD - Top 10 Lap Times",
                             True, (255, 215, 100))
    return {"title": title, "subtitle": subtitle, "hint": hint,
            "diff_hint": diff_hint, "header": header}

def _build_start_button(w, h, hovering):
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    rect = pygame.Rect(0, 0, w, h)
    if hovering:
        fill = (110, 220, 255, 245)
        border = (255, 255, 255, 240)
        border_w = 3
    else:
        fill = (60, 150, 220, 235)
        border = (180, 220, 255, 220)
        border_w = 2
    draw_rounded_panel(surf, rect, fill=fill, border=border,
                       radius=14, width=border_w)
    label = render_text_with_shadow(
        HUD_FONT, "START RACE  -  SPACE",
        color=(255, 255, 255), shadow_color=(0, 0, 0), offset=2)
    surf.blit(label,
              (rect.centerx - label.get_width() // 2,
               rect.centery - label.get_height() // 2))
    return surf

def _draw_diff_icon(surf, kind, cx, cy, color):
    """Draw a small stylised emblem for each difficulty tier."""
    if kind == "shield":

        pts = [
            (cx, cy - 16),
            (cx + 14, cy - 10),
            (cx + 14, cy + 4),
            (cx, cy + 18),
            (cx - 14, cy + 4),
            (cx - 14, cy - 10),
        ]
        pygame.draw.polygon(surf, color, pts)
        pygame.draw.polygon(surf, (15, 18, 32), pts, 2)

        pygame.draw.lines(surf, (15, 18, 32), False,
                          [(cx - 6, cy + 1), (cx - 1, cy + 6),
                           (cx + 7, cy - 5)], 3)
    elif kind == "bolt":

        pts = [
            (cx + 2, cy - 16),
            (cx - 8, cy + 2),
            (cx - 1, cy + 2),
            (cx - 4, cy + 16),
            (cx + 9, cy - 4),
            (cx + 1, cy - 4),
        ]
        pygame.draw.polygon(surf, color, pts)
        pygame.draw.polygon(surf, (40, 28, 0), pts, 2)
    elif kind == "skull":

        pygame.draw.circle(surf, color, (cx, cy - 2), 14)
        pygame.draw.rect(surf, color, (cx - 8, cy + 6, 16, 10),
                         border_radius=3)
        pygame.draw.circle(surf, (20, 10, 14), (cx - 5, cy - 3), 4)
        pygame.draw.circle(surf, (20, 10, 14), (cx + 5, cy - 3), 4)
        pygame.draw.rect(surf, (20, 10, 14), (cx - 2, cy + 3, 4, 6))

        pygame.draw.line(surf, (20, 10, 14),
                         (cx - 4, cy + 9), (cx - 4, cy + 14), 1)
        pygame.draw.line(surf, (20, 10, 14),
                         (cx, cy + 9), (cx, cy + 14), 1)
        pygame.draw.line(surf, (20, 10, 14),
                         (cx + 4, cy + 9), (cx + 4, cy + 14), 1)

def _build_difficulty_picker(selected_id):
    """Render the three difficulty cards into a single Surface."""
    card_w, card_h = 230, 138
    gap = 22
    n = len(DIFFICULTY_ORDER)
    total_w = card_w * n + gap * (n - 1)
    panel = pygame.Surface((total_w, card_h + 24), pygame.SRCALPHA)

    big_font = pygame.font.SysFont("comicsans", 28, bold=True)
    small_font = HUD_FONT_SMALL

    for i, key in enumerate(DIFFICULTY_ORDER):
        d = DIFFICULTIES[key]
        x = i * (card_w + gap)
        rect = pygame.Rect(x, 12, card_w, card_h)
        is_selected = (key == selected_id)
        accent = d["color"]

        if is_selected:

            glow_layers = 6
            for g in range(glow_layers, 0, -1):
                alpha = int(35 * (g / glow_layers))
                glow_rect = rect.inflate(g * 6, g * 6)
                glow = pygame.Surface((glow_rect.w, glow_rect.h),
                                      pygame.SRCALPHA)
                pygame.draw.rect(glow, accent + (alpha,),
                                 glow.get_rect(), border_radius=18)
                panel.blit(glow, glow_rect.topleft)
            fill = (32, 42, 70, 250)
            border = accent + (255,)
            border_w = 4
        else:
            fill = (16, 20, 36, 220)
            border = (90, 110, 140, 200)
            border_w = 2
        draw_rounded_panel(panel, rect, fill=fill, border=border,
                           radius=14, width=border_w)

        strip = pygame.Rect(rect.x + 10, rect.y + 8, rect.w - 20, 4)
        pygame.draw.rect(panel, accent, strip, border_radius=2)

        hk_rect = pygame.Rect(rect.x + 12, rect.y + 22, 26, 22)
        pygame.draw.rect(panel, accent, hk_rect, border_radius=6)
        hk = small_font.render(str(i + 1), True, (15, 18, 32))
        panel.blit(hk, (hk_rect.x + (hk_rect.w - hk.get_width()) // 2,
                        hk_rect.y + 2))

        _draw_diff_icon(panel, d.get("icon", "bolt"),
                        rect.right - 28, rect.y + 32, accent)

        label_color = accent if is_selected else (200, 215, 235)
        lbl = big_font.render(d["label"], True, label_color)
        panel.blit(lbl, (rect.x + (card_w - lbl.get_width()) // 2,
                         rect.y + 56))

        meter_y = rect.y + 92
        bar_count = 5
        bar_w = 14
        bar_gap = 4
        active_bars = {"EASY": 1, "MEDIUM": 3, "HARD": 5}.get(key, 3)
        meter_total = bar_count * bar_w + (bar_count - 1) * bar_gap
        meter_x = rect.x + (card_w - meter_total) // 2
        for b in range(bar_count):
            bx = meter_x + b * (bar_w + bar_gap)
            bar_h = 6 + b * 3
            by = meter_y + (18 - bar_h)
            color = accent if b < active_bars else (60, 70, 90)
            pygame.draw.rect(panel, color,
                             (bx, by, bar_w, bar_h), border_radius=2)

        desc_color = (220, 230, 245) if is_selected else (160, 180, 210)
        dsc = small_font.render(d["desc"], True, desc_color)
        panel.blit(dsc, (rect.x + (card_w - dsc.get_width()) // 2,
                         rect.y + card_h - 22))

        if is_selected:
            pygame.draw.line(panel, accent,
                             (rect.x + 16, rect.bottom - 4),
                             (rect.right - 16, rect.bottom - 4), 3)
    return panel

def _build_leaderboard_panel(leaderboard):
    """Render the leaderboard panel into one cached surface."""
    board_w, board_h = 400, 320
    panel = pygame.Surface((board_w, board_h), pygame.SRCALPHA)
    rect = pygame.Rect(0, 0, board_w, board_h)
    draw_rounded_panel(panel, rect,
                       fill=(15, 18, 32, 220),
                       border=(255, 215, 100, 220),
                       radius=14, width=2)
    entries = leaderboard.top(10)
    if not entries:
        empty = HUD_FONT_SMALL.render(
            "No entries yet. Be the first to set a lap time!",
            True, (200, 220, 230))
        panel.blit(empty, ((board_w - empty.get_width()) // 2, 60))
    else:
        for i, e in enumerate(entries):
            row_y = 50 + i * 24
            rank = HUD_FONT_SMALL.render(
                f"{i + 1:>2}.  {e['name'][:14]:<14}",
                True, (220, 230, 250))
            tval = HUD_FONT_SMALL.render(
                f"{e['lap_time']:.3f} s", True, (255, 220, 140))
            panel.blit(rank, (24, row_y))
            panel.blit(tval, (board_w - tval.get_width() - 24, row_y))
    return panel

def draw_start_screen(win, race_manager, leaderboard,
                      selected_difficulty="MEDIUM",
                      mouse_pos=(0, 0)):
    global _MENU_OVERLAY, _MENU_STATIC_CACHE, _MENU_LEADERBOARD_CACHE
    global _DIFFICULTY_PICKER_CACHE
    global _DIFFICULTY_CARD_RECTS, _START_BUTTON_RECT

    if _MENU_OVERLAY is None:
        overlay = pygame.Surface(win.get_size(), pygame.SRCALPHA)
        overlay.fill((5, 8, 20, 200))
        _MENU_OVERLAY = overlay
    if _MENU_STATIC_CACHE is None:
        _MENU_STATIC_CACHE = _build_menu_static()

    entries = leaderboard.top(10)
    sig = tuple((e["name"], round(e["lap_time"], 3)) for e in entries)
    if _MENU_LEADERBOARD_CACHE is None or _MENU_LEADERBOARD_CACHE[0] != sig:
        _MENU_LEADERBOARD_CACHE = (sig, _build_leaderboard_panel(leaderboard))

    if (_DIFFICULTY_PICKER_CACHE is None
            or _DIFFICULTY_PICKER_CACHE[0] != selected_difficulty):
        _DIFFICULTY_PICKER_CACHE = (
            selected_difficulty,
            _build_difficulty_picker(selected_difficulty),
        )

    win.blit(_MENU_OVERLAY, (0, 0))

    s = _MENU_STATIC_CACHE
    win.blit(s["title"],
             (WIDTH // 2 - s["title"].get_width() // 2, 36))
    win.blit(s["subtitle"],
             (WIDTH // 2 - s["subtitle"].get_width() // 2, 104))

    win.blit(s["diff_hint"],
             (WIDTH // 2 - s["diff_hint"].get_width() // 2, 142))
    picker = _DIFFICULTY_PICKER_CACHE[1]
    picker_x = WIDTH // 2 - picker.get_width() // 2
    picker_y = 168
    win.blit(picker, (picker_x, picker_y))

    card_w, card_h, gap = 230, 138, 22
    _DIFFICULTY_CARD_RECTS = {}
    for i, key in enumerate(DIFFICULTY_ORDER):
        _DIFFICULTY_CARD_RECTS[key] = pygame.Rect(
            picker_x + i * (card_w + gap),
            picker_y + 12,
            card_w, card_h,
        )

    global _START_BTN_CACHE
    btn_w, btn_h = 300, 60
    btn_rect = pygame.Rect(WIDTH // 2 - btn_w // 2,
                           picker_y + 12 + card_h + 22, btn_w, btn_h)
    _START_BUTTON_RECT = btn_rect
    if _START_BTN_CACHE is None or _START_BTN_CACHE[0] != (btn_w, btn_h):
        _START_BTN_CACHE = (
            (btn_w, btn_h),
            _build_start_button(btn_w, btn_h, hovering=False),
            _build_start_button(btn_w, btn_h, hovering=True),
        )
    hovering = btn_rect.collidepoint(mouse_pos)
    btn_surf = _START_BTN_CACHE[2] if hovering else _START_BTN_CACHE[1]
    win.blit(btn_surf, (btn_rect.x, btn_rect.y))

    win.blit(s["hint"],
             (WIDTH // 2 - s["hint"].get_width() // 2,
              btn_rect.bottom + 12))

    panel = _MENU_LEADERBOARD_CACHE[1]
    panel_x = WIDTH // 2 - panel.get_width() // 2
    panel_y = btn_rect.bottom + 44
    if panel_y + panel.get_height() > HEIGHT - 12:
        panel_y = HEIGHT - panel.get_height() - 12
    win.blit(panel, (panel_x, panel_y))
    win.blit(s["header"],
             (panel_x + (panel.get_width() - s["header"].get_width()) // 2,
              panel_y + 14))

    pygame.display.update()

def draw_waiting_overlay(win, race_manager, ai_racers):
    """Translucent banner shown after the player finishes while AI cars
    are still on track."""
    remaining = sum(1 for ai in ai_racers if ai.finish_time is None)
    if remaining == 0:
        return

    banner_w = 460
    banner_h = 70
    bx = WIDTH // 2 - banner_w // 2
    by = 12
    rect = pygame.Rect(bx, by, banner_w, banner_h)
    draw_rounded_panel(win, rect,
                       fill=(10, 14, 28, 200),
                       border=(255, 215, 100, 220),
                       radius=12, width=2)
    title = HUD_FONT.render("YOU FINISHED!", True, (255, 215, 100))
    win.blit(title,
             (bx + (banner_w - title.get_width()) // 2, by + 6))

    pf = race_manager.player_finish_time or 0.0
    sub = HUD_FONT_SMALL.render(
        f"Your time: {pf:.2f}s   Waiting for {remaining} opponent(s)..."
        f"   [ENTER to skip]",
        True, (220, 235, 250))
    win.blit(sub,
             (bx + (banner_w - sub.get_width()) // 2, by + 38))


# ---------------------------------------------------------------------------
# Results screen: trophies, stat tiles, podium, full panel renderer
# ---------------------------------------------------------------------------
_STAT_TILE_VAL_FONT = None

def _get_stat_tile_font():
    global _STAT_TILE_VAL_FONT
    if _STAT_TILE_VAL_FONT is None:
        _STAT_TILE_VAL_FONT = pygame.font.SysFont("comicsans", 28, bold=True)
    return _STAT_TILE_VAL_FONT

def _draw_trophy(surface, cx, cy, size, color):
    """Draw a stylised trophy emblem centred at (cx, cy)."""
    s = size

    cup_rect = pygame.Rect(cx - s, cy - s, s * 2, int(s * 1.4))
    pygame.draw.ellipse(surface, color,
                        (cup_rect.x, cup_rect.y, cup_rect.w, int(s * 0.35)))
    pygame.draw.rect(surface, color,
                     (cup_rect.x, cy - s + int(s * 0.15),
                      cup_rect.w, int(s * 0.95)))

    pygame.draw.polygon(surface, color, [
        (cx - s, cy + int(s * 0.10)),
        (cx + s, cy + int(s * 0.10)),
        (cx + int(s * 0.55), cy + int(s * 1.05)),
        (cx - int(s * 0.55), cy + int(s * 1.05)),
    ])

    handle_r = int(s * 0.65)
    pygame.draw.arc(surface, color,
                    (cx - s - handle_r, cy - s + 4,
                     handle_r * 2, int(s * 1.1)),
                    -1.4, 1.4, max(2, s // 8))
    pygame.draw.arc(surface, color,
                    (cx + s - handle_r, cy - s + 4,
                     handle_r * 2, int(s * 1.1)),
                    1.74, 4.54, max(2, s // 8))

    stem_w = int(s * 0.5)
    pygame.draw.rect(surface, color,
                     (cx - stem_w // 2, cy + int(s * 1.0),
                      stem_w, int(s * 0.45)))
    base_w = int(s * 1.4)
    pygame.draw.rect(surface, color,
                     (cx - base_w // 2, cy + int(s * 1.4),
                      base_w, int(s * 0.30)),
                     border_radius=4)

    sheen = (min(255, color[0] + 60), min(255, color[1] + 60),
             min(255, color[2] + 60))
    pygame.draw.line(surface, sheen,
                     (cx - int(s * 0.55), cy - int(s * 0.20)),
                     (cx - int(s * 0.55), cy + int(s * 0.65)),
                     max(2, s // 10))

    star_pts = []
    for k in range(10):
        ang = -math.pi / 2 + k * math.pi / 5
        rr = int(s * 0.35) if k % 2 == 0 else int(s * 0.15)
        star_pts.append((cx + math.cos(ang) * rr,
                         cy + int(s * 0.20) + math.sin(ang) * rr))
    pygame.draw.polygon(surface, (60, 50, 20), star_pts)

def _draw_confetti_layer(surface, palette, count=80, seed=0):
    """Scatter colourful confetti rectangles across the surface for a
    celebratory victory feel."""
    rng = random.Random(seed)
    w, h = surface.get_size()
    for _ in range(count):
        x = rng.randint(0, w - 1)
        y = rng.randint(40, h - 100)
        size_w = rng.randint(4, 9)
        size_h = rng.randint(8, 14)
        color = rng.choice(palette)
        alpha = rng.randint(140, 220)
        rot = rng.randint(0, 90)
        flake = pygame.Surface((size_w, size_h), pygame.SRCALPHA)
        flake.fill(color + (alpha,))
        flake = pygame.transform.rotate(flake, rot)
        surface.blit(flake, (x, y))

def _draw_stat_icon(surface, kind, cx, cy, size, color):
    """Tiny single-color icon for the stat tile."""
    s = size
    if kind == "stopwatch":
        pygame.draw.circle(surface, color, (cx, cy + 1), s)
        pygame.draw.circle(surface, (15, 18, 32), (cx, cy + 1), s, 2)
        pygame.draw.rect(surface, color,
                         (cx - 3, cy - s - 4, 6, 4), border_radius=1)
        pygame.draw.line(surface, (15, 18, 32),
                         (cx, cy + 1),
                         (cx + int(s * 0.6), cy - int(s * 0.4)), 2)
    elif kind == "speedo":
        pygame.draw.arc(surface, color,
                        (cx - s, cy - s, s * 2, s * 2),
                        math.pi * 0.15, math.pi * 0.85, 3)
        pygame.draw.line(surface, color,
                         (cx, cy + 2),
                         (cx + int(s * 0.7), cy - int(s * 0.4)), 2)
        pygame.draw.circle(surface, color, (cx, cy + 2), 3)
    elif kind == "flame":
        pts = [
            (cx, cy - s),
            (cx + s - 2, cy - 2),
            (cx + 3, cy + s),
            (cx - 3, cy + s),
            (cx - s + 2, cy - 2),
            (cx - 2, cy + 2),
        ]
        pygame.draw.polygon(surface, color, pts)
    elif kind == "crash":
        pts = [(cx, cy - s),
               (cx + 4, cy - 3), (cx + s, cy - 4),
               (cx + 5, cy + 2), (cx + s - 1, cy + s),
               (cx + 1, cy + 4), (cx - 4, cy + s),
               (cx - 5, cy + 2), (cx - s, cy - 1),
               (cx - 4, cy - 4)]
        pygame.draw.polygon(surface, color, pts)
    elif kind == "lap":
        pygame.draw.circle(surface, color, (cx, cy), s, 2)
        pygame.draw.line(surface, color,
                         (cx, cy - s + 1), (cx, cy + s - 1), 2)

_STAT_TILE_VAL_FONT_SMALL = None

def _get_stat_tile_font_small():
    global _STAT_TILE_VAL_FONT_SMALL
    if _STAT_TILE_VAL_FONT_SMALL is None:
        _STAT_TILE_VAL_FONT_SMALL = pygame.font.SysFont(
            "comicsans", 22, bold=True)
    return _STAT_TILE_VAL_FONT_SMALL

def _draw_stat_tile(surface, x, y, w, h, label, value, accent,
                    icon=None, compact=False):
    """Draw a polished "stat card" used on the results screen."""
    rect = pygame.Rect(x, y, w, h)

    shadow = pygame.Surface((w + 12, h + 12), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, 60),
                     (6, 8, w, h), border_radius=14)
    surface.blit(shadow, (x - 6, y - 4))

    inner = pygame.Surface((w, h), pygame.SRCALPHA)
    for i in range(h):
        t = i / h
        r = int(22 + (12 - 22) * t)
        g = int(28 + (16 - 28) * t)
        b = int(50 + (28 - 50) * t)
        pygame.draw.line(inner, (r, g, b), (0, i), (w, i))
    mask = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 245),
                     mask.get_rect(), border_radius=14)
    inner.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surface.blit(inner, (x, y))

    pygame.draw.rect(surface, accent + (200,), rect, 2, border_radius=14)

    strip_rect = pygame.Rect(x + 2, y + 2, w - 4, 6)
    pygame.draw.rect(surface, accent, strip_rect,
                     border_top_left_radius=12,
                     border_top_right_radius=12)

    pygame.draw.line(surface, (255, 255, 255, 35),
                     (x + 8, y + 14), (x + w - 8, y + 14), 1)

    label_x_start = x + 14
    if icon is not None:
        emblem_cx = x + 24
        emblem_cy = y + 30

        pygame.draw.circle(surface, (10, 14, 28), (emblem_cx, emblem_cy), 13)
        pygame.draw.circle(surface, accent, (emblem_cx, emblem_cy), 13, 1)
        _draw_stat_icon(surface, icon, emblem_cx, emblem_cy, 8, accent)
        label_x_start = x + 46
    lbl = HUD_FONT_SMALL.render(label, True, (200, 215, 240))
    lbl_y = y + (18 if compact else 24)
    surface.blit(lbl, (label_x_start, lbl_y))

    val_font = (_get_stat_tile_font_small() if compact
                else _get_stat_tile_font())
    val = val_font.render(value, True, accent)
    if val.get_width() > w - 12:
        val = _get_stat_tile_font_small().render(value, True, accent)
    val_y = y + h - val.get_height() - (6 if compact else 12)

    min_val_y = lbl_y + lbl.get_height() + 2
    if val_y < min_val_y:
        val_y = min_val_y
    surface.blit(val, (x + (w - val.get_width()) // 2, val_y))

def _draw_podium(surface, x, y, w, h, top3):
    """Draw a stylised 3-D podium visualization for the top 3."""
    base_y = y + h - 4

    heights = {1: int(h * 0.62), 2: int(h * 0.46), 3: int(h * 0.34)}
    block_w = 64
    gap = 12

    order = [2, 1, 3]
    total_w = block_w * 3 + gap * 2
    start_x = x + (w - total_w) // 2
    medal_colors = {1: (255, 215, 100), 2: (220, 225, 235),
                    3: (215, 160, 105)}
    medal_dark = {1: (160, 120, 30), 2: (130, 135, 150),
                  3: (135, 90, 50)}

    by_rank = {s["rank"]: s for s in top3}

    shadow = pygame.Surface((total_w + 20, 12), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 80), shadow.get_rect())
    surface.blit(shadow, (start_x - 10, base_y))

    rank_font = pygame.font.SysFont("comicsans", 30, bold=True)
    nm_font = pygame.font.SysFont("comicsans", 16, bold=True)

    for i, rank in enumerate(order):
        if rank not in by_rank:
            continue
        s = by_rank[rank]
        bx = start_x + i * (block_w + gap)
        bh = heights[rank]
        color = medal_colors[rank]
        dark = medal_dark[rank]

        for row in range(bh):
            t = row / max(1, bh - 1)
            r = int(color[0] + (dark[0] - color[0]) * t * 0.7)
            g = int(color[1] + (dark[1] - color[1]) * t * 0.7)
            b = int(color[2] + (dark[2] - color[2]) * t * 0.7)
            pygame.draw.line(surface, (r, g, b),
                             (bx, base_y - bh + row),
                             (bx + block_w, base_y - bh + row))

        pygame.draw.rect(surface, color,
                         (bx, base_y - bh, block_w, 8),
                         border_top_left_radius=8,
                         border_top_right_radius=8)

        side = pygame.Surface((6, bh), pygame.SRCALPHA)
        side.fill((0, 0, 0, 70))
        surface.blit(side, (bx + block_w - 6, base_y - bh))

        pygame.draw.rect(surface, (255, 255, 255, 90),
                         (bx + 4, base_y - bh + 2, block_w - 12, 3),
                         border_radius=2)

        pygame.draw.rect(surface, dark,
                         (bx, base_y - bh, block_w, bh), 2,
                         border_top_left_radius=8,
                         border_top_right_radius=8)

        rk = rank_font.render(str(rank), True, (40, 32, 10))
        surface.blit(rk, (bx + (block_w - rk.get_width()) // 2,
                          base_y - bh + bh // 2 - rk.get_height() // 2))

        swatch_y = base_y - bh - 38
        swatch_x = bx + block_w // 2

        for g_i in range(4, 0, -1):
            alpha = int(35 * (g_i / 4))
            glow = pygame.Surface((28, 28), pygame.SRCALPHA)
            pygame.draw.circle(glow, color + (alpha,), (14, 14), 10 + g_i)
            surface.blit(glow, (swatch_x - 14, swatch_y - 6))
        pygame.draw.circle(surface, s["color"],
                           (swatch_x, swatch_y + 8), 10)
        pygame.draw.circle(surface, (255, 255, 255),
                           (swatch_x, swatch_y + 8), 10, 2)

        if rank == 1:
            sw_cy = swatch_y + 8
            pygame.draw.circle(surface, (255, 215, 100),
                               (swatch_x, sw_cy), 13, 2)

        raw = s["name"].replace("[YOU]", "").strip()
        if raw.lower() == "you":
            abbr = "YOU"
        else:
            abbr = raw[:3].upper()
        nm = nm_font.render(abbr, True, (255, 255, 255))
        surface.blit(nm, (bx + (block_w - nm.get_width()) // 2,
                          base_y - bh - 20))

def _build_results_panel(race_manager, standings, new_best,
                         panel_size=None, difficulty="MEDIUM"):
    """Render the entire results overlay onto a single cached surface.

    Premium "race report" layout with:
      - Smooth navy gradient + subtle radial glow background
      - Big hero header with trophy + dynamic accent color
      - Glassmorphic standings card with a glowing player row
      - Five icon stat tiles
      - 3-D podium + lap-times chart

    The panel is sized to ``panel_size`` (defaults to the current display
    size) so it always fully covers the background — the previous version
    used the track-image dimensions, which left grass showing at the top
    and bottom on displays with a different aspect ratio.
    """
    if panel_size is None:
        panel_size = WIN.get_size()

    WIDTH, HEIGHT = panel_size

    CONTENT_W = min(WIDTH - 80, 1080)
    CONTENT_X = (WIDTH - CONTENT_W) // 2

    COMPACT = HEIGHT <= 820

    surface = pygame.Surface((WIDTH, HEIGHT))

    for i in range(HEIGHT):
        t = i / HEIGHT

        r = int(14 + (6 - 14) * t)
        g = int(20 + (8 - 20) * t)
        b = int(38 + (16 - 38) * t)
        pygame.draw.line(surface, (max(0, r), max(0, g), max(0, b)),
                         (0, i), (WIDTH, i))
    surface = surface.convert_alpha()

    big_glow = pygame.Surface((WIDTH, 460), pygame.SRCALPHA)

    player_rank = next((s["rank"] for s in standings
                        if s["is_player"]), 1)
    if player_rank == 1:
        title_text = "VICTORY"
        title_color = (255, 220, 110)
        subtitle_text = "P1  ·  CHAMPION OF THE GRID"
        glow_color = (255, 200, 80)
        accent = (255, 215, 100)
        trophy_color = (255, 215, 100)
        show_confetti = True
    elif player_rank == 2:
        title_text = "PODIUM FINISH"
        title_color = (220, 230, 245)
        subtitle_text = "P2  ·  STRONG PERFORMANCE"
        glow_color = (180, 200, 230)
        accent = (210, 215, 230)
        trophy_color = (210, 215, 230)
        show_confetti = True
    elif player_rank == 3:
        title_text = "PODIUM FINISH"
        title_color = (220, 175, 120)
        subtitle_text = "P3  ·  ON THE PODIUM"
        glow_color = (200, 140, 90)
        accent = (210, 160, 110)
        trophy_color = (210, 160, 110)
        show_confetti = True
    else:
        title_text = "RACE COMPLETE"
        title_color = (220, 230, 250)
        subtitle_text = f"P{player_rank}  ·  KEEP PUSHING"
        glow_color = (110, 150, 220)
        accent = (140, 180, 240)
        trophy_color = None
        show_confetti = False

    cx, cy = WIDTH // 2, 200
    for r in range(420, 30, -8):
        alpha = int(38 * (1 - r / 420) ** 2.4)
        if alpha <= 0:
            continue
        pygame.draw.circle(big_glow, glow_color + (alpha,), (cx, cy), r)
    surface.blit(big_glow, (0, -40))

    if show_confetti:
        palette = [
            (255, 215, 100),
            (255, 130, 230),
            (120, 220, 255),
            (140, 230, 150),
        ]
        _draw_confetti_layer(surface, palette, count=28, seed=player_rank)

    pygame.draw.rect(surface, accent + (220,), (0, 0, WIDTH, 3))
    pygame.draw.rect(surface, accent + (220,),
                     (0, HEIGHT - 3, WIDTH, 3))

    for i in range(8):
        alpha = int(60 * (1 - i / 8))
        pygame.draw.rect(surface, (0, 0, 0, alpha),
                         (0, 3 + i, WIDTH, 1))

    if COMPACT:
        title_size = 46
    elif CONTENT_W >= 900:
        title_size = 68
    else:
        title_size = 58
    big_title_font = pygame.font.SysFont("comicsans", title_size, bold=True)
    title = render_text_with_shadow(
        big_title_font, title_text,
        color=title_color, shadow_color=(0, 0, 0), offset=4)
    title_x = WIDTH // 2 - title.get_width() // 2
    title_y = 14 if COMPACT else 28
    surface.blit(title, (title_x, title_y))

    subt_font = pygame.font.SysFont("comicsans",
                                    18 if COMPACT else 22, bold=True)
    subt = subt_font.render(subtitle_text, True, accent)
    surface.blit(subt,
                 (WIDTH // 2 - subt.get_width() // 2,
                  title_y + title.get_height() + (2 if COMPACT else 6)))

    diff_color_map = {
        "EASY": (110, 220, 140),
        "MEDIUM": (255, 215, 100),
        "HARD": (240, 90, 110),
    }
    diff_col = diff_color_map.get(difficulty, accent)
    winner = next((s for s in standings if s["rank"] == 1), None)
    winner_name = winner["name"] if winner else "-"
    winner_time = (f"{winner['finish_time']:.2f}s"
                   if winner and winner["finish_time"] is not None else "—")
    chip_specs = [
        ("MODE", difficulty, diff_col),
        ("LAPS", "3 / 3", (120, 200, 255)),
        ("WINNER", f"{winner_name}  {winner_time}", (255, 215, 100)),
    ]
    chip_font_lbl = pygame.font.SysFont("comicsans",
                                        10 if COMPACT else 11, bold=True)
    chip_font_val = pygame.font.SysFont("comicsans",
                                        13 if COMPACT else 16, bold=True)
    chip_pad_x = 9 if COMPACT else 12
    chip_pad_y = 2 if COMPACT else 4
    chip_h = chip_font_val.get_height() + chip_font_lbl.get_height() + 4
    rendered_chips = []
    for lbl, val, col in chip_specs:
        lbl_s = chip_font_lbl.render(lbl, True, (180, 200, 230))
        val_s = chip_font_val.render(val, True, col)
        cw = max(lbl_s.get_width(), val_s.get_width()) + chip_pad_x * 2
        rendered_chips.append((lbl_s, val_s, col, cw))
    chip_gap = 10
    chips_total_w = (sum(c[3] for c in rendered_chips)
                     + chip_gap * (len(rendered_chips) - 1))
    chips_x = WIDTH // 2 - chips_total_w // 2
    chips_y = (title_y + title.get_height()
               + subt.get_height() + (2 if COMPACT else 8))
    cx_cursor = chips_x
    for lbl_s, val_s, col, cw in rendered_chips:
        chip_rect = pygame.Rect(cx_cursor, chips_y, cw, chip_h + chip_pad_y)

        chip_bg = pygame.Surface((chip_rect.w, chip_rect.h),
                                 pygame.SRCALPHA)
        for i in range(chip_rect.h):
            tt = i / max(1, chip_rect.h - 1)
            chip_bg.fill((22 + int(8 * (1 - tt)),
                          28 + int(10 * (1 - tt)),
                          50 + int(14 * (1 - tt)), 235),
                         (0, i, chip_rect.w, 1))
        mask = pygame.Surface((chip_rect.w, chip_rect.h), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255),
                         mask.get_rect(), border_radius=10)
        chip_bg.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        surface.blit(chip_bg, chip_rect.topleft)
        pygame.draw.rect(surface, col + (200,), chip_rect,
                         1, border_radius=10)

        pygame.draw.line(surface, col + (220,),
                         (chip_rect.x + 8, chip_rect.y + 1),
                         (chip_rect.x + chip_rect.w - 8, chip_rect.y + 1), 1)
        surface.blit(lbl_s, (chip_rect.x +
                             (chip_rect.w - lbl_s.get_width()) // 2,
                             chip_rect.y + 4))
        surface.blit(val_s, (chip_rect.x +
                             (chip_rect.w - val_s.get_width()) // 2,
                             chip_rect.y + 4 + lbl_s.get_height() + 1))
        cx_cursor += cw + chip_gap

    hero_line_y = chips_y + chip_h + (4 if COMPACT else 14)
    pygame.draw.line(surface, accent + (90,),
                     (WIDTH // 2 - 240, hero_line_y),
                     (WIDTH // 2 + 240, hero_line_y), 1)

    pygame.draw.polygon(surface, accent,
                        [(WIDTH // 2, hero_line_y - 4),
                         (WIDTH // 2 + 5, hero_line_y),
                         (WIDTH // 2, hero_line_y + 4),
                         (WIDTH // 2 - 5, hero_line_y)])

    fastest_lap_value = None
    fastest_lap_name = None
    for s in standings:
        bl = s.get("best_lap")
        if bl is None:
            continue
        if fastest_lap_value is None or bl < fastest_lap_value:
            fastest_lap_value = bl
            fastest_lap_name = s["name"]

    if COMPACT:
        row_h = 36
        header_band = 32
        col_band = 22
        bottom_pad = 10
        badge_outer = 13
        badge_inner = 10
    else:
        row_h = 44
        header_band = 42
        col_band = 30
        bottom_pad = 18
        badge_outer = 17
        badge_inner = 14
    table_w = min(CONTENT_W, 880)
    table_h = (header_band + col_band
               + row_h * len(standings) + bottom_pad)
    table_x = WIDTH // 2 - table_w // 2
    table_y = hero_line_y + (12 if COMPACT else 20)
    table_rect = pygame.Rect(table_x, table_y, table_w, table_h)

    shadow = pygame.Surface((table_w + 24, table_h + 24), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, 90),
                     (12, 14, table_w, table_h), border_radius=22)
    surface.blit(shadow, (table_x - 12, table_y - 12))

    draw_rounded_panel(surface, table_rect,
                       fill=(18, 24, 44, 245),
                       border=accent + (180,),
                       radius=20, width=2)

    pygame.draw.line(surface, (255, 255, 255, 30),
                     (table_x + 16, table_y + 4),
                     (table_x + table_w - 16, table_y + 4), 1)

    for i in range(header_band):
        t = i / header_band
        c1 = (32, 46, 86)
        c2 = (24, 32, 58)
        cr = int(c1[0] + (c2[0] - c1[0]) * t)
        cg = int(c1[1] + (c2[1] - c1[1]) * t)
        cb = int(c1[2] + (c2[2] - c1[2]) * t)
        pygame.draw.line(surface, (cr, cg, cb),
                         (table_x + 2, table_y + 2 + i),
                         (table_x + table_w - 2, table_y + 2 + i))

    pygame.draw.rect(surface, (18, 24, 44, 0),
                     (table_x, table_y, table_w, header_band),
                     border_top_left_radius=20,
                     border_top_right_radius=20)

    band_surf = pygame.Surface((table_w - 4, header_band), pygame.SRCALPHA)
    for i in range(header_band):
        t = i / header_band
        c = (int(32 + (24 - 32) * t), int(46 + (32 - 46) * t),
             int(86 + (58 - 86) * t))
        pygame.draw.line(band_surf, c, (0, i), (table_w - 4, i))
    rounded_band = pygame.Surface((table_w - 4, header_band),
                                  pygame.SRCALPHA)
    pygame.draw.rect(rounded_band, (255, 255, 255, 255),
                     rounded_band.get_rect(),
                     border_top_left_radius=18, border_top_right_radius=18)
    band_surf.blit(rounded_band, (0, 0),
                   special_flags=pygame.BLEND_RGBA_MIN)
    surface.blit(band_surf, (table_x + 2, table_y + 2))

    header_font = pygame.font.SysFont("comicsans",
                                      18 if COMPACT else 22, bold=True)
    header = header_font.render("RACE STANDINGS", True, accent)
    header_y = table_y + (header_band - header.get_height()) // 2
    surface.blit(header,
                 (table_x + (table_w - header.get_width()) // 2,
                  header_y))

    col_rank_x = table_x + int(table_w * 0.05)
    col_driver_x = table_x + int(table_w * 0.15)
    col_fl_x = table_x + int(table_w * 0.44)
    col_best_x = table_x + int(table_w * 0.51)
    col_gap_x = table_x + int(table_w * 0.69)
    col_total_x = table_x + int(table_w * 0.84)

    col_y = table_y + header_band + 4
    for label, x in (
        ("RANK", col_rank_x),
        ("DRIVER", col_driver_x),
        ("BEST LAP", col_best_x),
        ("GAP", col_gap_x),
        ("TOTAL", col_total_x),
    ):
        lbl_surf = HUD_FONT_SMALL.render(label, True, (140, 170, 210))
        surface.blit(lbl_surf, (x, col_y))

    leader_time = next((s["finish_time"] for s in standings
                        if s["rank"] == 1
                        and s["finish_time"] is not None), None)

    medal_colors = {1: (255, 215, 100), 2: (220, 225, 235),
                    3: (215, 160, 105)}
    row_font = (pygame.font.SysFont("comicsans", 18, bold=True)
                if COMPACT else HUD_FONT)
    for i, s in enumerate(standings):
        row_y = table_y + header_band + col_band + i * row_h
        rank_color = medal_colors.get(s["rank"], (170, 190, 220))
        text_color = (255, 255, 255) if s["is_player"] else (230, 238, 252)

        text_h = row_font.get_height()
        text_y = row_y + (row_h - 4 - text_h) // 2

        row_bg = pygame.Rect(table_x + 14, row_y, table_w - 28, row_h - 4)

        if s["is_player"]:

            grad = pygame.Surface((row_bg.w, row_bg.h), pygame.SRCALPHA)
            for col_i in range(row_bg.w):
                t = col_i / row_bg.w
                a = int(180 * (1 - t * 0.6))
                grad.fill((accent[0] // 3, accent[1] // 3,
                           min(255, accent[2] // 3 + 40), a),
                          (col_i, 0, 1, row_bg.h))
            mask = pygame.Surface((row_bg.w, row_bg.h), pygame.SRCALPHA)
            pygame.draw.rect(mask, (255, 255, 255, 255),
                             mask.get_rect(), border_radius=10)
            grad.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            surface.blit(grad, row_bg.topleft)

            edge = pygame.Rect(row_bg.x, row_bg.y, 4, row_bg.h)
            pygame.draw.rect(surface, accent, edge,
                             border_top_left_radius=10,
                             border_bottom_left_radius=10)

            for k in range(2, 0, -1):
                alpha = int(45 / k)
                halo = row_bg.inflate(k * 2, k * 2)
                pygame.draw.rect(surface, accent + (alpha,), halo,
                                 1, border_radius=12)
        elif i % 2 == 0:
            pygame.draw.rect(surface, (24, 32, 56), row_bg,
                             border_radius=10)

        if s["rank"] in medal_colors and not s["is_player"]:
            edge = pygame.Rect(row_bg.x, row_bg.y, 4, row_bg.h)
            pygame.draw.rect(surface, rank_color, edge,
                             border_top_left_radius=10,
                             border_bottom_left_radius=10)

        badge_cx = col_rank_x + badge_outer
        badge_cy = row_y + (row_h - 4) // 2
        if s["rank"] in medal_colors:
            pygame.draw.circle(surface, rank_color,
                               (badge_cx, badge_cy), badge_outer)
            pygame.draw.circle(surface, (15, 18, 32),
                               (badge_cx, badge_cy), badge_inner)
            rank_text_color = rank_color
        else:
            pygame.draw.circle(surface, (60, 80, 120),
                               (badge_cx, badge_cy), badge_outer - 1)
            pygame.draw.circle(surface, (15, 18, 32),
                               (badge_cx, badge_cy), badge_inner - 1)
            rank_text_color = (200, 215, 240)
        rank_lbl = row_font.render(str(s["rank"]), True, rank_text_color)
        surface.blit(rank_lbl,
                     (badge_cx - rank_lbl.get_width() // 2,
                      badge_cy - rank_lbl.get_height() // 2 - 1))

        swatch_x = col_driver_x - 14
        swatch_y = badge_cy
        pygame.draw.circle(surface, s["color"],
                           (swatch_x, swatch_y), 8)
        pygame.draw.circle(surface, (255, 255, 255),
                           (swatch_x, swatch_y), 8, 2)

        name = s["name"]
        if s["is_player"]:
            name += "  [YOU]"
        surface.blit(row_font.render(name, True, text_color),
                     (col_driver_x + 6, text_y))

        bl = s.get("best_lap")
        is_fastest = (bl is not None and fastest_lap_value is not None
                      and abs(bl - fastest_lap_value) < 1e-3)
        if is_fastest:
            tag_h = text_h + 4
            tag_rect = pygame.Rect(col_fl_x,
                                   row_y + (row_h - 4 - tag_h) // 2,
                                   36, tag_h)
            pygame.draw.rect(surface, (255, 130, 230), tag_rect,
                             border_radius=6)
            tag = HUD_FONT_SMALL.render("FL", True, (40, 10, 30))
            surface.blit(tag,
                         (tag_rect.x + (tag_rect.w - tag.get_width()) // 2,
                          tag_rect.y + (tag_rect.h - tag.get_height()) // 2))

        if bl is not None:
            bl_color = (255, 130, 230) if is_fastest else text_color
            bl_str = f"{bl:.2f}s"
        else:
            bl_color = (140, 150, 170)
            bl_str = "-"
        surface.blit(row_font.render(bl_str, True, bl_color),
                     (col_best_x, text_y))

        if s["finish_time"] is None:
            gap_str = "DNF"
            gap_color = (255, 130, 130)
        elif s["rank"] == 1 or leader_time is None:
            gap_str = "—"
            gap_color = (160, 175, 200)
        else:
            gap_str = f"+{s['finish_time'] - leader_time:.2f}s"
            gap_color = (200, 215, 245)
        surface.blit(row_font.render(gap_str, True, gap_color),
                     (col_gap_x, text_y))

        if s["finish_time"] is not None:
            time_str = f"{s['finish_time']:.2f}s"
        else:
            time_str = f"DNF (L{s['lap']})"
        surface.blit(row_font.render(time_str, True, text_color),
                     (col_total_x, text_y))

    summary = race_manager.race_summary()
    max_kmh = int(summary["max_speed"] * KMH_FACTOR)
    your_best = summary["best_lap"]
    your_best_str = f"{your_best:.2f}s" if your_best else "-"

    tiles = [
        ("RACE BEST",
         f"{fastest_lap_value:.2f}s" if fastest_lap_value else "-",
         (255, 130, 230), "stopwatch"),
        ("YOUR BEST", your_best_str, (120, 220, 255), "lap"),
        ("TOP SPEED", f"{max_kmh} km/h", (255, 200, 90), "speedo"),
        ("CRASHES", str(summary["collisions"]), (255, 130, 130), "crash"),
        ("NITRO USED", f"{summary['nitro_duration']:.1f}s",
         (255, 170, 80), "flame"),
    ]
    gap = 14
    tiles_total_w = min(table_w, CONTENT_W)
    tile_w = (tiles_total_w - gap * (len(tiles) - 1)) // len(tiles)
    tile_h = 74 if COMPACT else 92
    total_w = tile_w * len(tiles) + gap * (len(tiles) - 1)
    tx0 = WIDTH // 2 - total_w // 2
    ty = table_y + table_h + (28 if COMPACT else 44)

    section = HUD_FONT_SMALL.render("RACE STATS", True, accent)
    section_y = ty - section.get_height() - 6
    surface.blit(section, (tx0, section_y))

    for i, (lbl, val, col, icon) in enumerate(tiles):
        _draw_stat_tile(surface, tx0 + i * (tile_w + gap), ty,
                        tile_w, tile_h, lbl, val, col, icon=icon,
                        compact=COMPACT)

    bottom_y = ty + tile_h + (16 if COMPACT else 36)

    bottom_h = HEIGHT - bottom_y - (48 if COMPACT else 64)
    if bottom_h < 130:
        bottom_h = 130

    panel_total_w = total_w
    panel_x = tx0
    podium_w = max(260, int(panel_total_w * 0.30))
    chart_w = panel_total_w - podium_w - 18
    chart_x = panel_x + podium_w + 18

    def _draw_glass_panel(rect, border_color):

        shadow = pygame.Surface((rect.w + 16, rect.h + 16),
                                pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 80),
                         (8, 10, rect.w, rect.h), border_radius=18)
        surface.blit(shadow, (rect.x - 8, rect.y - 4))

        inner = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        for i in range(rect.h):
            t = i / rect.h
            r = int(22 + (12 - 22) * t)
            g = int(28 + (16 - 28) * t)
            b = int(50 + (28 - 50) * t)
            pygame.draw.line(inner, (r, g, b), (0, i), (rect.w, i))
        mask = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 245),
                         mask.get_rect(), border_radius=18)
        inner.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        surface.blit(inner, rect.topleft)
        pygame.draw.rect(surface, border_color + (200,),
                         rect, 2, border_radius=18)

        pygame.draw.line(surface, (255, 255, 255, 35),
                         (rect.x + 12, rect.y + 6),
                         (rect.x + rect.w - 12, rect.y + 6), 1)

    podium_rect = pygame.Rect(panel_x, bottom_y, podium_w, bottom_h)
    _draw_glass_panel(podium_rect, accent)

    pod_title = HUD_FONT_SMALL.render("PODIUM", True, accent)
    surface.blit(pod_title, (panel_x + 14, bottom_y + 10))
    pod_under_y = bottom_y + 10 + pod_title.get_height() + 2
    pygame.draw.line(surface, accent + (140,),
                     (panel_x + 14, pod_under_y),
                     (panel_x + 14 + pod_title.get_width(),
                      pod_under_y), 1)
    top3 = [s for s in standings if s["rank"] <= 3]
    _draw_podium(surface, panel_x + 12, bottom_y + 28,
                 podium_w - 24, bottom_h - 38, top3)

    chart_rect = pygame.Rect(chart_x, bottom_y, chart_w, bottom_h)
    _draw_glass_panel(chart_rect, (120, 200, 255))
    title_lbl = HUD_FONT_SMALL.render("YOUR LAP TIMES", True,
                                      (120, 200, 255))
    title_lbl_x = chart_x + (chart_w - title_lbl.get_width()) // 2
    surface.blit(title_lbl, (title_lbl_x, bottom_y + 10))

    underline_y = bottom_y + 10 + title_lbl.get_height() + 2
    pygame.draw.line(surface, (120, 200, 255, 140),
                     (title_lbl_x, underline_y),
                     (title_lbl_x + title_lbl.get_width(),
                      underline_y), 1)

    if summary["lap_times"]:
        slowest = max(summary["lap_times"])
        fastest = min(summary["lap_times"])
        avg_lap = sum(summary["lap_times"]) / len(summary["lap_times"])
        n = len(summary["lap_times"])
        avail_h = bottom_h - 56
        bar_h = min(34, max(20, (avail_h - (n - 1) * 12) // n))
        gap_v = 12
        block_h = bar_h * n + gap_v * (n - 1)
        chart_inner_y = bottom_y + 46 + (avail_h - block_h) // 2
        bar_max_w = chart_w - 140
        bar_x = chart_x + 60

        avg_ratio = (slowest - avg_lap) / (slowest - fastest + 1e-6)
        avg_x = bar_x + int(bar_max_w * (0.35 + 0.65 * avg_ratio))
        for ydash in range(chart_inner_y - 4,
                           chart_inner_y + block_h + 4, 6):
            pygame.draw.line(surface, (255, 220, 130, 180),
                             (avg_x, ydash), (avg_x, ydash + 3), 1)

        avg_tag = HUD_FONT_SMALL.render(f"AVG  {avg_lap:.2f}s", True,
                                        (255, 220, 130))
        surface.blit(avg_tag,
                     (chart_x + chart_w - avg_tag.get_width() - 14,
                      bottom_y + 14))
        for i, t in enumerate(summary["lap_times"]):
            row_y = chart_inner_y + i * (bar_h + gap_v)
            lbl = HUD_FONT.render(f"L{i+1}", True, (200, 220, 240))
            surface.blit(lbl, (chart_x + 16,
                               row_y + bar_h // 2 - lbl.get_height() // 2))

            bg_rect = pygame.Rect(bar_x, row_y, bar_max_w, bar_h)
            pygame.draw.rect(surface, (28, 36, 60), bg_rect,
                             border_radius=6)

            ratio = (slowest - t) / (slowest - fastest + 1e-6)
            fill_w = int(bar_max_w * (0.35 + 0.65 * ratio))
            is_best = abs(t - fastest) < 1e-3
            base_col = ((255, 130, 230) if is_best else (120, 200, 255))
            grad_bar = pygame.Surface((fill_w, bar_h), pygame.SRCALPHA)
            for col_i in range(fill_w):
                tt = col_i / max(1, fill_w - 1)
                rr = int(base_col[0] * (0.65 + 0.35 * tt))
                gg = int(base_col[1] * (0.65 + 0.35 * tt))
                bb = int(base_col[2] * (0.65 + 0.35 * tt))
                pygame.draw.line(grad_bar, (rr, gg, bb),
                                 (col_i, 0), (col_i, bar_h))
            mb = pygame.Surface((fill_w, bar_h), pygame.SRCALPHA)
            pygame.draw.rect(mb, (255, 255, 255, 255),
                             mb.get_rect(), border_radius=6)
            grad_bar.blit(mb, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            surface.blit(grad_bar, (bar_x, row_y))

            pygame.draw.line(surface, (255, 255, 255, 90),
                             (bar_x + 6, row_y + 3),
                             (bar_x + fill_w - 6, row_y + 3), 1)
            pygame.draw.rect(surface, base_col + (220,), bg_rect,
                             1, border_radius=6)
            t_lbl = HUD_FONT.render(
                f"{t:.2f}s", True, (255, 255, 255))
            surface.blit(t_lbl, (bar_x + bar_max_w + 12,
                                 row_y + bar_h // 2 - t_lbl.get_height() // 2))

    if new_best:
        nb_pad_x = 12
        nb_pad_y = 4
        nb_text = HUD_FONT_SMALL.render("NEW BEST LAP",
                                        True, (40, 28, 6))
        nb_w = nb_text.get_width() + nb_pad_x * 2
        nb_h = nb_text.get_height() + nb_pad_y * 2
        nb_rect = pygame.Rect(WIDTH - nb_w - 22, 20, nb_w, nb_h)
        draw_rounded_panel(surface, nb_rect,
                           fill=(255, 215, 100, 230),
                           border=(255, 215, 100, 255),
                           radius=8, width=1)
        surface.blit(nb_text, (nb_rect.x + nb_pad_x,
                               nb_rect.y + nb_pad_y))

    key_font = HUD_FONT
    parts = [
        ("[R]", accent),
        (" RACE AGAIN     ", (220, 235, 250)),
        ("[ESC]", (255, 130, 130)),
        (" QUIT", (220, 235, 250)),
    ]
    rendered = [key_font.render(t, True, c) for t, c in parts]
    total_w_p = sum(r.get_width() for r in rendered)
    px = WIDTH // 2 - total_w_p // 2
    py = HEIGHT - 36
    for r in rendered:
        surface.blit(r, (px, py))
        px += r.get_width()
    return surface

def draw_results_screen(win, race_manager, leaderboard, standings,
                        new_best=False, difficulty="MEDIUM"):
    global _RESULTS_PANEL_CACHE

    win_size = win.get_size()
    sig = (
        new_best,
        win_size,
        difficulty,
        tuple((s["rank"], s["name"], s["finish_time"], s["lap"],
               s.get("best_lap")) for s in standings),
    )
    if _RESULTS_PANEL_CACHE is None or _RESULTS_PANEL_CACHE[0] != sig:
        _RESULTS_PANEL_CACHE = (
            sig,
            _build_results_panel(race_manager, standings, new_best,
                                 panel_size=win_size,
                                 difficulty=difficulty),
        )

    win.blit(_RESULTS_PANEL_CACHE[1], (0, 0))
    pygame.display.update()


# ---------------------------------------------------------------------------
# Race setup: AI roster, start-lights gantry, countdown overlay
# ---------------------------------------------------------------------------
def _build_ai_racers(difficulty="MEDIUM"):

    preset = DIFFICULTIES.get(difficulty, DIFFICULTIES["MEDIUM"])
    sm = preset["ai_speed_mult"]
    rm = preset["ai_rotation_mult"]
    lb = preset["ai_lookahead_bonus"]
    apex = preset.get("ai_apex_strength", 0.7)
    corner = preset.get("ai_corner_aggression", 1.0)
    accel = preset.get("ai_accel_rate", 0.07)
    start = PlayerCar.START_POS
    common = dict(
        max_vel=4.5 * sm, rotation_vel=4.5 * rm,
        path=PATH, start_offset=0, start_pos=start,
        border_mask=TRACK_BORDER_MASK, safety_margin=14,
        apex_strength=apex, corner_aggression=corner,
        accel_rate=accel,
    )

    driver_pool = [
        dict(name="Verstappen", accent_color=(190, 130, 230),
             racing_line_offset=8,  lookahead_bias=8),
        dict(name="Hamilton",   accent_color=(120, 200, 255),
             racing_line_offset=4,  lookahead_bias=4),
        dict(name="Leclerc",    accent_color=(110, 230, 130),
             racing_line_offset=-2, lookahead_bias=-6),
        dict(name="Norris",     accent_color=(255, 180, 90),
             racing_line_offset=-4, lookahead_bias=2),
        dict(name="Russell",    accent_color=(230, 230, 240),
             racing_line_offset=-6, lookahead_bias=0),
    ]
    car_sprites = [PURPLE_CAR, WHITE_CAR, GREEN_CAR]

    chosen = random.sample(driver_pool, k=len(car_sprites))
    random.shuffle(car_sprites)

    racers = []
    for sprite, profile in zip(car_sprites, chosen):
        racers.append(

            AIRacer(
                profile["name"], sprite,
                accent_color=profile["accent_color"],
                racing_line_offset=profile["racing_line_offset"],
                lookahead_bias=profile["lookahead_bias"] + lb,
                **common,
            )
        )
    return racers

COUNTDOWN_SECONDS = 4.5
_LIGHT_INTERVAL = 0.7
_LIGHTS_OUT_AT = _LIGHT_INTERVAL * 5
_RACE_BEGINS_AT = _LIGHTS_OUT_AT

_COUNTDOWN_DIM_CACHE = None
_COUNTDOWN_GANTRY_CACHE = None
_COUNTDOWN_GO_TEXT = None
_COUNTDOWN_READY_TEXT = None

def _build_lights_gantry(width, height):
    """Render the dark steel gantry frame the lights sit in."""
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    body = pygame.Rect(0, 0, width, height)
    draw_rounded_panel(surf, body,
                       fill=(18, 20, 26, 245),
                       border=(80, 90, 110, 255),
                       radius=18, width=3)

    inner_pad = 14
    inner = pygame.Rect(inner_pad, inner_pad,
                        width - inner_pad * 2, height - inner_pad * 2)
    pygame.draw.rect(surf, (8, 10, 14), inner, border_radius=12)
    pygame.draw.rect(surf, (45, 55, 75), inner, 2, border_radius=12)

    pygame.draw.rect(surf, (60, 65, 80), (-4, height // 2 - 8, 12, 16),
                     border_radius=4)
    pygame.draw.rect(surf, (60, 65, 80),
                     (width - 8, height // 2 - 8, 12, 16),
                     border_radius=4)
    return surf

def _draw_light(surf, cx, cy, radius, lit, color_on):
    """Draw a single round bulb. When lit, emit a soft glow halo."""

    pygame.draw.circle(surf, (10, 10, 14), (cx, cy), radius + 4)
    pygame.draw.circle(surf, (50, 55, 70), (cx, cy), radius + 4, 2)
    if lit:

        glow_layers = 4
        for i in range(glow_layers, 0, -1):
            alpha = int(45 * (i / glow_layers) ** 2)
            r = radius + 4 + i * 2
            glow = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(glow, color_on + (alpha,), (r + 2, r + 2), r)
            surf.blit(glow, (cx - r - 2, cy - r - 2))
        pygame.draw.circle(surf, color_on, (cx, cy), radius)

        hi = (min(255, color_on[0] + 60),
              min(255, color_on[1] + 80),
              min(255, color_on[2] + 80))
        pygame.draw.circle(surf, hi,
                           (cx - radius // 3, cy - radius // 3),
                           max(2, radius // 3))
    else:

        pygame.draw.circle(surf, (28, 28, 36), (cx, cy), radius)
        pygame.draw.circle(surf, (55, 60, 75), (cx, cy), radius, 1)

def _draw_countdown_overlay(win, elapsed):
    """F1-style 5-light start sequence centred on screen.

    `elapsed` is seconds since the countdown was triggered.
    """
    global _COUNTDOWN_DIM_CACHE, _COUNTDOWN_GANTRY_CACHE
    global _COUNTDOWN_GO_TEXT, _COUNTDOWN_READY_TEXT

    if _COUNTDOWN_DIM_CACHE is None:
        dim = pygame.Surface(win.get_size(), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 130))
        _COUNTDOWN_DIM_CACHE = dim
    if _COUNTDOWN_READY_TEXT is None:
        _COUNTDOWN_READY_TEXT = HUD_FONT.render(
            "Lights are coming on...", True, (220, 235, 250))
    if _COUNTDOWN_GO_TEXT is None:
        big_font = pygame.font.SysFont("comicsans", 120, bold=True)
        _COUNTDOWN_GO_TEXT = render_text_with_shadow(
            big_font, "GO! GO! GO!",
            color=(120, 255, 140), shadow_color=(0, 0, 0), offset=5)

    win.blit(_COUNTDOWN_DIM_CACHE, (0, 0))

    if elapsed < _LIGHTS_OUT_AT:
        lit_count = min(5, int(elapsed / _LIGHT_INTERVAL) + 1)
        all_red = (lit_count == 5)

        gantry_w = 520
        gantry_h = 130
        if (_COUNTDOWN_GANTRY_CACHE is None
                or _COUNTDOWN_GANTRY_CACHE[0] != (gantry_w, gantry_h)):
            _COUNTDOWN_GANTRY_CACHE = (
                (gantry_w, gantry_h),
                _build_lights_gantry(gantry_w, gantry_h),
            )
        gx = WIDTH // 2 - gantry_w // 2
        gy = HEIGHT // 2 - gantry_h // 2 - 20

        bulb_surf = _COUNTDOWN_GANTRY_CACHE[1].copy()
        radius = 28
        spacing = 88
        cy = gantry_h // 2
        start_x = (gantry_w - spacing * 4) // 2
        for i in range(5):
            cx = start_x + i * spacing
            _draw_light(bulb_surf, cx, cy, radius, i < lit_count,
                        (240, 40, 40))
        win.blit(bulb_surf, (gx, gy))

        if all_red:
            sub_text = HUD_FONT.render(
                "All 5 lights on -- wait for lights out!",
                True, (255, 220, 110))
        else:
            sub_text = _COUNTDOWN_READY_TEXT
        win.blit(sub_text,
                 (WIDTH // 2 - sub_text.get_width() // 2,
                  gy + gantry_h + 18))
    else:

        win.blit(_COUNTDOWN_GO_TEXT,
                 (WIDTH // 2 - _COUNTDOWN_GO_TEXT.get_width() // 2,
                  HEIGHT // 2 - _COUNTDOWN_GO_TEXT.get_height() // 2))

    pygame.display.update()


# ---------------------------------------------------------------------------
# Main game loop
# ---------------------------------------------------------------------------
def main():
    global _MENU_BG_SNAPSHOT, _RESULTS_BG_SNAPSHOT, _RESULTS_PANEL_CACHE

    track = Track(TRACK_SURFACE, TRACK_BORDER, TRACK_BORDER_MASK,
                  FINISH, FINISH_POSITION, PATH)
    player_car = PlayerCar(max_vel=4.5, rotation_vel=2.5)
    race_manager = RaceManager()
    stats_logger = StatsLogger(file_path=asset_path("stats"))
    leaderboard = Leaderboard(file_path=asset_path("leaderboard.csv"))

    selected_difficulty = "MEDIUM"
    preset = DIFFICULTIES[selected_difficulty]
    player_car.nitro_max = preset["nitro_max"]
    obstacles = spawn_obstacles(PATH, count=preset["obstacles"], seed=42)
    nitro_pads = [NitroPad(p) for p in NITRO_PAD_POSITIONS]
    ai_racers = _build_ai_racers(selected_difficulty)

    clock = pygame.time.Clock()
    finish_state = {"was_on": False, "just_finished": False}
    state = "menu"
    last_summary_logged = False
    new_best = False
    final_standings = []
    countdown_started_at = None

    def begin_countdown():
        """Reset everything and place cars on the grid, then enter the
        'countdown' state so the player has time to brace before the
        race timer starts."""
        nonlocal obstacles, ai_racers, finish_state, last_summary_logged
        nonlocal new_best, final_standings, state, countdown_started_at
        preset_local = DIFFICULTIES[selected_difficulty]
        player_car.nitro_max = preset_local["nitro_max"]
        obstacles = spawn_obstacles(
            PATH, count=preset_local["obstacles"], seed=42)
        ai_racers = _build_ai_racers(selected_difficulty)

        race_manager.reset_game()
        player_car.reset()
        for ob in obstacles:
            ob.active = True
            ob._was_hitting = False
        for pad in nitro_pads:
            pad.cooldown = 0
        for ai in ai_racers:
            ai.reset()
        finish_state = {"was_on": False, "just_finished": False}
        last_summary_logged = False
        new_best = False
        final_standings = []
        countdown_started_at = time.time()
        state = "countdown"

    def begin_race():
        """Lights-out: actually start the race timer + AI motion."""
        nonlocal state
        race_manager.start_race()
        stats_logger.start_race()
        race_start = race_manager._race_start_time
        for ai in ai_racers:
            ai.start(race_start)
        state = "racing"

    run = True
    while run:
        dt = clock.tick(FPS) / 1000.0
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    run = False
                elif event.key == pygame.K_F11:
                    pygame.display.toggle_fullscreen()
                elif state == "menu" and event.key in (pygame.K_1,
                                                        pygame.K_KP1):
                    selected_difficulty = "EASY"
                    _MENU_BG_SNAPSHOT = None
                elif state == "menu" and event.key in (pygame.K_2,
                                                        pygame.K_KP2):
                    selected_difficulty = "MEDIUM"
                    _MENU_BG_SNAPSHOT = None
                elif state == "menu" and event.key in (pygame.K_3,
                                                        pygame.K_KP3):
                    selected_difficulty = "HARD"
                    _MENU_BG_SNAPSHOT = None
                elif state == "menu" and event.key == pygame.K_SPACE:
                    begin_countdown()
                elif state == "results" and event.key == pygame.K_r:
                    _RESULTS_BG_SNAPSHOT = None
                    _RESULTS_PANEL_CACHE = None
                    _MENU_BG_SNAPSHOT = None
                    state = "menu"
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if state == "menu":

                    clicked_card = None
                    for key, rect in _DIFFICULTY_CARD_RECTS.items():
                        if rect.collidepoint(event.pos):
                            clicked_card = key
                            break
                    if clicked_card is not None:
                        selected_difficulty = clicked_card
                        _MENU_BG_SNAPSHOT = None
                    elif (_START_BUTTON_RECT is not None
                          and _START_BUTTON_RECT.collidepoint(event.pos)):
                        begin_countdown()

        if state == "menu":
            if _MENU_BG_SNAPSHOT is None:
                standings = compute_standings(player_car, ai_racers,
                                              race_manager, PATH)
                draw_world(WIN, track, obstacles, nitro_pads,
                           player_car, ai_racers, race_manager, standings,
                           show_overlays=False)
                _MENU_BG_SNAPSHOT = WIN.copy()
            else:
                WIN.blit(_MENU_BG_SNAPSHOT, (0, 0))
            draw_start_screen(WIN, race_manager, leaderboard,
                              selected_difficulty, mouse_pos=mouse_pos)
            continue

        if state == "countdown":

            global _COUNTDOWN_BG_SNAPSHOT
            if _COUNTDOWN_BG_SNAPSHOT is None:
                standings = compute_standings(player_car, ai_racers,
                                              race_manager, PATH)
                draw_world(WIN, track, obstacles, nitro_pads,
                           player_car, ai_racers, race_manager, standings,
                           show_overlays=False)
                _COUNTDOWN_BG_SNAPSHOT = WIN.copy()
            else:
                WIN.blit(_COUNTDOWN_BG_SNAPSHOT, (0, 0))
            elapsed = time.time() - countdown_started_at
            if elapsed >= _RACE_BEGINS_AT:
                _COUNTDOWN_BG_SNAPSHOT = None
                begin_race()
                go_started_at = time.time()

                while time.time() - go_started_at < 0.4:
                    for ev in pygame.event.get():
                        if ev.type == pygame.QUIT:
                            run = False
                            break
                    if not run:
                        break
                    standings = compute_standings(player_car, ai_racers,
                                                  race_manager, PATH)
                    draw_world(WIN, track, obstacles, nitro_pads,
                               player_car, ai_racers, race_manager,
                               standings, show_overlays=True)
                    WIN.blit(_COUNTDOWN_GO_TEXT,
                             (WIDTH // 2 - _COUNTDOWN_GO_TEXT.get_width()
                              // 2,
                              80))
                    pygame.display.update()
                    clock.tick(FPS)
            else:
                _draw_countdown_overlay(WIN, elapsed)
            continue

        if state == "racing":
            keys = pygame.key.get_pressed()

            if (race_manager.player_finished
                    and (keys[pygame.K_RETURN]
                         or keys[pygame.K_KP_ENTER])):
                for ai in ai_racers:
                    if ai.finish_time is None:
                        ai.finish_time = time.time() - race_manager._race_start_time

            if not race_manager.player_finished:
                nitro_requested = (keys[pygame.K_LSHIFT]
                                   or keys[pygame.K_RSHIFT])
                player_car.update_nitro(dt, nitro_requested)

                handle_input(player_car, race_manager, keys, stats_logger)
                handle_obstacles_and_nitro(player_car, obstacles, nitro_pads,
                                           race_manager, dt, stats_logger)
                finish_state = handle_track_collision(
                    player_car, track, race_manager, finish_state,
                    stats_logger)

                race_manager.update_max_speed(player_car.vel)
                stats_logger.sample_speed(abs(player_car.vel))
            else:

                player_car.update_nitro(dt, False)
                player_car.apply_friction()

            for ai in ai_racers:
                ai.update(race_manager.TOTAL_LAPS)

            standings = compute_standings(player_car, ai_racers,
                                          race_manager, PATH)
            draw_world(WIN, track, obstacles, nitro_pads,
                       player_car, ai_racers, race_manager, standings)

            if race_manager.player_finished:
                draw_waiting_overlay(WIN, race_manager, ai_racers)

            all_finished = (
                race_manager.player_finished
                and all(ai.finish_time is not None for ai in ai_racers)
            )

            if all_finished and not last_summary_logged:
                race_manager.end_race()
                summary = race_manager.race_summary()
                stats_logger.log_race_summary(summary)
                final_standings = compute_standings(
                    player_car, ai_racers, race_manager, PATH,
                    race_finished=True)
                stats_logger.log_competitor_results(final_standings)
                stats_logger.export_to_csv()
                if generate_report is not None:
                    try:
                        report_path = generate_report(
                            stats_dir=asset_path("stats"),
                            out_dir=asset_path("reports"),
                            open_browser=False,
                        )
                        if report_path:
                            print(f"[stats] report updated -> "
                                  f"{report_path}")
                            print("[stats] open it with:  "
                                  "python visualize.py")
                    except Exception as exc:
                        print(f"[stats] could not build dashboard: {exc}")
                if summary["best_lap"] is not None:
                    before = leaderboard.top(leaderboard.MAX_ENTRIES)
                    worst_before = (before[-1]["lap_time"]
                                    if len(before) >= leaderboard.MAX_ENTRIES
                                    else float("inf"))
                    leaderboard.submit("Player", summary["best_lap"])
                    new_best = summary["best_lap"] < worst_before
                last_summary_logged = True
                state = "results"
            continue

        if state == "results":
            if _RESULTS_BG_SNAPSHOT is None:
                draw_world(WIN, track, obstacles, nitro_pads,
                           player_car, ai_racers, race_manager,
                           final_standings, show_overlays=False)
                _RESULTS_BG_SNAPSHOT = WIN.copy()
            else:
                WIN.blit(_RESULTS_BG_SNAPSHOT, (0, 0))
            draw_results_screen(WIN, race_manager, leaderboard,
                                final_standings, new_best,
                                difficulty=selected_difficulty)

    pygame.quit()

if __name__ == "__main__":
    main()
