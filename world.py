"""Track view rendering and per-frame gameplay helpers."""
import math

import pygame

from assets import GRASS
from settings import KMH_FACTOR
from utils import draw_vignette

from hud import (
    draw_hud,
    draw_minimap,
    draw_speedometer,
    draw_standings_panel,
)

_FLAME_SPRITES = []


def draw_world(win, track, obstacles, nitro_pads, player_car, ai_racers,
               race_manager, standings=None, show_overlays=True,
               update_display=True):
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
    if update_display:
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
