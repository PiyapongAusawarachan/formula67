"""Post-race results overlay (standings, stats, podium, lap chart)."""
import math
import random

import pygame

from assets import HUD_FONT, HUD_FONT_SMALL, WIN
from settings import KMH_FACTOR
from utils import draw_rounded_panel, render_text_with_shadow

_RESULTS_PANEL_CACHE = None
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
