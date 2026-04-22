"""Compute race positions for HUD and results."""


def player_progress_score(player_car, race_manager, path):
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
        "progress": player_progress_score(player_car, race_manager, path),
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
