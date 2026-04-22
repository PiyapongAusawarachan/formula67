"""Pygame display setup, fonts, and loaded images (depends on settings scales)."""
import os

import pygame

from settings import TRACK_SCALE, _PATH_SCALE
from utils import scale_image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def asset_path(*parts):
    """Return an absolute path to a bundled asset (cross-platform safe)."""
    return os.path.join(BASE_DIR, *parts)


pygame.font.init()

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
    """Open the game window. Try fullscreen first, then fall back."""
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
