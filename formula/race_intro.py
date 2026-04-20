"""AI grid setup and F1-style pre-race countdown overlay."""
import random

import pygame

from ai_racer import AIRacer
from assets import (
    GREEN_CAR,
    HUD_FONT,
    PURPLE_CAR,
    TRACK_BORDER_MASK,
    WHITE_CAR,
    WIDTH,
    HEIGHT,
)
from car import PlayerCar
from settings import DIFFICULTIES, LIGHT_INTERVAL, LIGHTS_OUT_AT, PATH
from utils import draw_rounded_panel, render_text_with_shadow


def build_ai_racers(difficulty="MEDIUM"):
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


_COUNTDOWN_DIM_CACHE = None
_COUNTDOWN_GANTRY_CACHE = None
COUNTDOWN_GO_TEXT = None
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


def draw_countdown_overlay(win, elapsed):
    """F1-style 5-light start sequence centred on screen.

    `elapsed` is seconds since the countdown was triggered.
    """
    global _COUNTDOWN_DIM_CACHE, _COUNTDOWN_GANTRY_CACHE
    global COUNTDOWN_GO_TEXT, _COUNTDOWN_READY_TEXT

    if _COUNTDOWN_DIM_CACHE is None:
        dim = pygame.Surface(win.get_size(), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 130))
        _COUNTDOWN_DIM_CACHE = dim
    if _COUNTDOWN_READY_TEXT is None:
        _COUNTDOWN_READY_TEXT = HUD_FONT.render(
            "Lights are coming on...", True, (220, 235, 250))
    if COUNTDOWN_GO_TEXT is None:
        big_font = pygame.font.SysFont("comicsans", 120, bold=True)
        COUNTDOWN_GO_TEXT = render_text_with_shadow(
            big_font, "GO! GO! GO!",
            color=(120, 255, 140), shadow_color=(0, 0, 0), offset=5)

    win.blit(_COUNTDOWN_DIM_CACHE, (0, 0))

    if elapsed < LIGHTS_OUT_AT:
        lit_count = min(5, int(elapsed / LIGHT_INTERVAL) + 1)
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

        win.blit(COUNTDOWN_GO_TEXT,
                 (WIDTH // 2 - COUNTDOWN_GO_TEXT.get_width() // 2,
                  HEIGHT // 2 - COUNTDOWN_GO_TEXT.get_height() // 2))

    pygame.display.update()
