"""Formula 67 entry point (game loop lives here; rest is split across modules)."""
import time

import pygame

import race_intro
import screen_menu
import screen_results
from assets import (
    FINISH,
    FINISH_POSITION,
    HEIGHT,
    PLAYFIELD_RECT,
    TRACK_BORDER,
    TRACK_BORDER_MASK,
    TRACK_SURFACE,
    WIDTH,
    WIN,
    asset_path,
)
from car import PlayerCar
from obstacle import NitroPad, spawn_obstacles
from race import RaceManager
from race_intro import build_ai_racers, draw_countdown_overlay
from screen_menu import draw_start_screen, draw_waiting_overlay
from settings import (
    DIFFICULTIES,
    DIFFICULTY_ORDER,
    FPS,
    MENU_FPS,
    NITRO_PAD_POSITIONS,
    PATH,
    RACE_BEGINS_AT,
)
from stats import Leaderboard, StatsLogger
from standings import compute_standings, player_progress_score
from telemetry_extra import (
    SectorTimer,
    gap_progress_units,
    nearest_path_index,
)
from track import Track
from world import (
    draw_world,
    handle_input,
    handle_obstacles_and_nitro,
    handle_track_collision,
)


def _import_visualize():
    """matplotlib/pandas are heavy — load only when charts are needed."""
    try:
        mod = __import__(
            "visualize",
            fromlist=["build_embedded_telemetry_viewer", "generate_report"],
        )
        return mod.build_embedded_telemetry_viewer, mod.generate_report
    except ImportError:
        return None, None


_MENU_BG_SNAPSHOT = None
_RESULTS_BG_SNAPSHOT = None
_COUNTDOWN_BG_SNAPSHOT = None


def main():
    global _MENU_BG_SNAPSHOT, _RESULTS_BG_SNAPSHOT
    global _COUNTDOWN_BG_SNAPSHOT

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
    ai_racers = build_ai_racers(selected_difficulty)

    clock = pygame.time.Clock()
    finish_state = {"was_on": False, "just_finished": False,
                    "lap_started_next": False}
    state = "menu"
    last_summary_logged = False
    new_best = False
    final_standings = []
    countdown_started_at = None
    telemetry_viewer = None
    visualization_return = "menu"
    sector_timer = SectorTimer()

    def try_open_visualization(from_state: str):
        nonlocal telemetry_viewer, visualization_return, state
        build_embedded_telemetry_viewer, _ = _import_visualize()
        if build_embedded_telemetry_viewer is None:
            return
        viewer = build_embedded_telemetry_viewer(
            stats_dir=asset_path("stats"),
            out_dir=asset_path("reports"),
        )
        if viewer is None:
            print("[game] No telemetry yet — finish at least one race "
                  "(stats exported) to view charts.")
            return
        telemetry_viewer = viewer
        visualization_return = from_state
        state = "visualization"

    def begin_countdown():
        nonlocal obstacles, ai_racers, finish_state, last_summary_logged
        nonlocal new_best, final_standings, state, countdown_started_at
        preset_local = DIFFICULTIES[selected_difficulty]
        player_car.nitro_max = preset_local["nitro_max"]
        obstacles = spawn_obstacles(
            PATH, count=preset_local["obstacles"], seed=42)
        ai_racers = build_ai_racers(selected_difficulty)

        race_manager.reset_game()
        player_car.reset()
        for ob in obstacles:
            ob.active = True
            ob._was_hitting = False
        for pad in nitro_pads:
            pad.cooldown = 0
        for ai in ai_racers:
            ai.reset()
        finish_state = {"was_on": False, "just_finished": False,
                        "lap_started_next": False}
        last_summary_logged = False
        new_best = False
        final_standings = []
        countdown_started_at = time.time()
        state = "countdown"

    def begin_race():
        nonlocal state
        race_manager.start_race()
        stats_logger.start_race()
        sector_timer.on_race_start(time.time())
        race_start = race_manager._race_start_time
        for ai in ai_racers:
            ai.start(race_start)
        state = "racing"

    run = True
    while run:
        tick_rate = MENU_FPS if state == "menu" else FPS
        dt = clock.tick(tick_rate) / 1000.0
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
            elif (state == "visualization" and telemetry_viewer is not None):
                popped = telemetry_viewer.handle_event(event)
                if popped == "pop":
                    state = visualization_return
                    telemetry_viewer = None
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    run = False
                elif event.key == pygame.K_F11:
                    pygame.display.toggle_fullscreen()
                    _MENU_BG_SNAPSHOT = None
                    _COUNTDOWN_BG_SNAPSHOT = None
                    _RESULTS_BG_SNAPSHOT = None
                    screen_menu.invalidate_menu_caches()
                elif state == "menu" and event.key in (pygame.K_1,
                                                        pygame.K_KP1):
                    selected_difficulty = "EASY"
                elif state == "menu" and event.key in (pygame.K_2,
                                                        pygame.K_KP2):
                    selected_difficulty = "MEDIUM"
                elif state == "menu" and event.key in (pygame.K_3,
                                                        pygame.K_KP3):
                    selected_difficulty = "HARD"
                elif state == "menu" and event.key in (
                        pygame.K_LEFT, pygame.K_a):
                    i = DIFFICULTY_ORDER.index(selected_difficulty)
                    selected_difficulty = DIFFICULTY_ORDER[
                        (i - 1) % len(DIFFICULTY_ORDER)]
                elif state == "menu" and event.key in (
                        pygame.K_RIGHT, pygame.K_d):
                    i = DIFFICULTY_ORDER.index(selected_difficulty)
                    selected_difficulty = DIFFICULTY_ORDER[
                        (i + 1) % len(DIFFICULTY_ORDER)]
                elif state == "menu" and event.key == pygame.K_SPACE:
                    begin_countdown()
                elif state == "menu" and event.key == pygame.K_v:
                    try_open_visualization("menu")
                elif state == "results" and event.key == pygame.K_r:
                    _RESULTS_BG_SNAPSHOT = None
                    screen_results._RESULTS_PANEL_CACHE = None
                    _MENU_BG_SNAPSHOT = None
                    state = "menu"
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if state == "menu":

                    clicked_card = None
                    for key, rect in screen_menu._DIFFICULTY_CARD_RECTS.items():
                        if rect.collidepoint(event.pos):
                            clicked_card = key
                            break
                    if clicked_card is not None:
                        selected_difficulty = clicked_card
                    elif (screen_menu._START_BUTTON_RECT is not None
                          and screen_menu._START_BUTTON_RECT.collidepoint(
                              event.pos)):
                        begin_countdown()
                    elif (screen_menu._TELEMETRY_MENU_RECT is not None
                          and screen_menu._TELEMETRY_MENU_RECT.collidepoint(
                              event.pos)):
                        try_open_visualization("menu")

        if state == "menu":
            if _MENU_BG_SNAPSHOT is None:
                standings = compute_standings(player_car, ai_racers,
                                              race_manager, PATH)
                draw_world(WIN, track, obstacles, nitro_pads,
                           player_car, ai_racers, race_manager, standings,
                           show_overlays=False, update_display=False)
                _MENU_BG_SNAPSHOT = WIN.copy()
            draw_start_screen(WIN, _MENU_BG_SNAPSHOT, race_manager, leaderboard,
                              selected_difficulty, mouse_pos=mouse_pos)
            continue

        if state == "visualization" and telemetry_viewer is not None:
            telemetry_viewer.draw(WIN)
            pygame.display.flip()
            continue

        if state == "countdown":

            if _COUNTDOWN_BG_SNAPSHOT is None:
                standings = compute_standings(player_car, ai_racers,
                                              race_manager, PATH)
                draw_world(WIN, track, obstacles, nitro_pads,
                           player_car, ai_racers, race_manager, standings,
                           show_overlays=False, update_display=False)
                _COUNTDOWN_BG_SNAPSHOT = WIN.copy()
            else:
                WIN.blit(_COUNTDOWN_BG_SNAPSHOT, (0, 0))
            elapsed = time.time() - countdown_started_at
            if elapsed >= RACE_BEGINS_AT:
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
                    go = race_intro.COUNTDOWN_GO_TEXT
                    WIN.blit(go,
                             (PLAYFIELD_RECT.centerx - go.get_width() // 2,
                              PLAYFIELD_RECT.centery - go.get_height() // 2))
                    pygame.display.update()
                    clock.tick(FPS)
            else:
                draw_countdown_overlay(WIN, elapsed)
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
                if finish_state.get("lap_started_next"):
                    sector_timer.on_new_lap(time.time())
                    finish_state["lap_started_next"] = False

                race_manager.update_max_speed(player_car.vel)
                standings = compute_standings(player_car, ai_racers,
                                              race_manager, PATH)
                cx = player_car.x + player_car.img.get_width() / 2
                cy = player_car.y + player_car.img.get_height() / 2
                pidx = nearest_path_index(player_car, PATH)
                pprog = player_progress_score(player_car, race_manager, PATH)
                gap = gap_progress_units(standings, pprog)
                stats_logger.telemetry_bundle(
                    abs(player_car.vel),
                    cx, cy, pidx, race_manager.current_lap,
                    keys[pygame.K_w] or keys[pygame.K_UP],
                    keys[pygame.K_s] or keys[pygame.K_DOWN],
                    nitro_requested,
                    gap,
                )
                sector_timer.tick(
                    player_car, track.checkpoints,
                    race_manager.current_lap,
                    stats_logger.race_id,
                    stats_logger,
                    time.time(),
                )
            else:

                player_car.update_nitro(dt, False)
                player_car.apply_friction()

            for ai in ai_racers:
                ai.update(race_manager.TOTAL_LAPS)

            standings = compute_standings(player_car, ai_racers,
                                          race_manager, PATH)

            if race_manager.player_finished:
                draw_world(WIN, track, obstacles, nitro_pads,
                           player_car, ai_racers, race_manager, standings,
                           show_overlays=True)
                draw_waiting_overlay(WIN, race_manager, ai_racers)
            else:
                draw_world(WIN, track, obstacles, nitro_pads,
                           player_car, ai_racers, race_manager, standings,
                           show_overlays=True)

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
                           final_standings, show_overlays=False,
                           update_display=False)
                _RESULTS_BG_SNAPSHOT = WIN.copy()
            else:
                WIN.blit(_RESULTS_BG_SNAPSHOT, (0, 0))
            screen_results.draw_results_screen(
                WIN, race_manager, leaderboard,
                final_standings, new_best,
                difficulty=selected_difficulty)
            continue

    pygame.quit()


if __name__ == "__main__":
    main()
