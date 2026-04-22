"""In-race HUD: lap/time panel, speedometer, minimap, standings."""
import math

import pygame

from assets import HUD_FONT, HUD_FONT_SMALL, HEIGHT, WIDTH
from settings import KMH_FACTOR, PATH, SPEEDO_MAX_KMH
from utils import draw_progress_bar, draw_rounded_panel

_HUD_LABEL_CACHE = {}
_MINIMAP_PATH_SURFACE = None
_SPEEDO_BASE = None
_SPEEDO_DIGIT_FONT = None


def _get_speedo_digit_font():
    global _SPEEDO_DIGIT_FONT
    if _SPEEDO_DIGIT_FONT is None:
        _SPEEDO_DIGIT_FONT = pygame.font.SysFont("comicsans", 24, bold=True)
    return _SPEEDO_DIGIT_FONT


def _get_label(text, color=(170, 200, 230)):
    key = (text, color)
    cached = _HUD_LABEL_CACHE.get(key)
    if cached is None:
        cached = HUD_FONT_SMALL.render(text, True, color)
        _HUD_LABEL_CACHE[key] = cached
    return cached


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
    """Map t in [0,1] to a point on a 270-degree arc gauge."""
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
