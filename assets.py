"""Bitmaps + window from ``imgs/`` (sizes follow settings).

Coordinate systems:
    **Track space** — ``Car.x/y``, PATH, masks, nitro/obstacle positions: origin
    is the top-left of the track bitmap. Physics and mask overlap use this space.

    **Screen space** — use ``track_to_screen()`` or ``PLAYFIELD_RECT`` for blits;
    the track bitmap is placed at ``PLAYFIELD_RECT.topleft``.
"""
import os

import pygame

from settings import (
    HUD_SIDEBAR_WIDTH,
    PLAYFIELD_MARGIN_BOTTOM,
    PLAYFIELD_MARGIN_LEFT,
    PLAYFIELD_MARGIN_TOP,
    TRACK_SCALE,
    _PATH_SCALE,
)
from utils import scale_image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def asset_path(*parts):
    """``imgs/foo.png`` style path next to this package."""
    return os.path.join(BASE_DIR, *parts)


pygame.font.init()

GRASS_SRC = scale_image(pygame.image.load(asset_path("imgs", "grass.png")),
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

# Playfield (track + car coords) vs full pygame window (includes right HUD rail).
TRACK_VIEW_W, TRACK_VIEW_H = TRACK_SURFACE.get_width(), TRACK_SURFACE.get_height()
PLAYFIELD_X = PLAYFIELD_MARGIN_LEFT
PLAYFIELD_Y = PLAYFIELD_MARGIN_TOP
PLAYFIELD_RECT = pygame.Rect(
    PLAYFIELD_X, PLAYFIELD_Y, TRACK_VIEW_W, TRACK_VIEW_H)
WIDTH = PLAYFIELD_MARGIN_LEFT + TRACK_VIEW_W + HUD_SIDEBAR_WIDTH
HEIGHT = PLAYFIELD_MARGIN_TOP + TRACK_VIEW_H + PLAYFIELD_MARGIN_BOTTOM
GRASS = pygame.transform.smoothscale(GRASS_SRC, (WIDTH, HEIGHT))


def track_to_screen(x: float, y: float) -> tuple[float, float]:
    """Map track-bitmap coordinates to window/screen coordinates."""
    return x + PLAYFIELD_X, y + PLAYFIELD_Y


def _create_window(width, height):
    """Fullscreen if possible, else windowed."""
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
