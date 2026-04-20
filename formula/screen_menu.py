"""Main menu: difficulty cards, start button, leaderboard panel."""
import pygame

from assets import (
    HEIGHT,
    HUD_FONT,
    HUD_FONT_SMALL,
    TITLE_FONT,
    WIDTH,
)
from settings import DIFFICULTIES, DIFFICULTY_ORDER
from utils import draw_rounded_panel, render_text_with_shadow

_MENU_OVERLAY = None
_MENU_STATIC_CACHE = None
_MENU_LEADERBOARD_CACHE = None
_DIFFICULTY_PICKER_CACHE = None
_DIFFICULTY_CARD_RECTS = {}
_START_BUTTON_RECT = None
_START_BTN_CACHE = None

# Full-screen menu layer (everything except Start button) — rebuilt only when
# difficulty, leaderboard, or window size changes. Saves heavy per-frame draws.
_MENU_COMPOSITE = None
_MENU_COMPOSITE_SIG = None

# Track snapshot + composite merged (one blit instead of two per frame).
_MENU_MERGED_BASE = None
_MENU_MERGED_SIG = None


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
        "Choose: click card · keys 1-3 · arrows or A/D",
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

            glow_layers = 3
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


def _invalidate_menu_composite():
    global _MENU_COMPOSITE, _MENU_COMPOSITE_SIG
    global _MENU_MERGED_BASE, _MENU_MERGED_SIG
    _MENU_COMPOSITE = None
    _MENU_COMPOSITE_SIG = None
    _MENU_MERGED_BASE = None
    _MENU_MERGED_SIG = None


def invalidate_menu_caches():
    """After fullscreen/resize or when rebuilding the track snapshot, drop menu
    pixel caches so layers match the display."""
    _invalidate_menu_composite()


def draw_start_screen(win, track_snapshot, race_manager, leaderboard,
                      selected_difficulty="MEDIUM",
                      mouse_pos=(0, 0)):
    global _MENU_OVERLAY, _MENU_STATIC_CACHE, _MENU_LEADERBOARD_CACHE
    global _DIFFICULTY_PICKER_CACHE
    global _DIFFICULTY_CARD_RECTS, _START_BUTTON_RECT
    global _START_BTN_CACHE
    global _MENU_COMPOSITE, _MENU_COMPOSITE_SIG
    global _MENU_MERGED_BASE, _MENU_MERGED_SIG

    w, h = win.get_size()

    if _MENU_OVERLAY is None or _MENU_OVERLAY.get_size() != (w, h):
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((5, 8, 20, 200))
        _MENU_OVERLAY = overlay
        _invalidate_menu_composite()

    if _MENU_STATIC_CACHE is None:
        _MENU_STATIC_CACHE = _build_menu_static()

    entries = leaderboard.top(10)
    lb_sig = tuple((e["name"], round(e["lap_time"], 3)) for e in entries)
    if _MENU_LEADERBOARD_CACHE is None or _MENU_LEADERBOARD_CACHE[0] != lb_sig:
        _MENU_LEADERBOARD_CACHE = (lb_sig, _build_leaderboard_panel(leaderboard))
        _invalidate_menu_composite()

    if (_DIFFICULTY_PICKER_CACHE is None
            or _DIFFICULTY_PICKER_CACHE[0] != selected_difficulty):
        _DIFFICULTY_PICKER_CACHE = (
            selected_difficulty,
            _build_difficulty_picker(selected_difficulty),
        )
        _invalidate_menu_composite()

    composite_sig = (selected_difficulty, lb_sig, (w, h))
    if _MENU_COMPOSITE is None or _MENU_COMPOSITE_SIG != composite_sig:
        comp = pygame.Surface((w, h), pygame.SRCALPHA)
        comp.blit(_MENU_OVERLAY, (0, 0))

        s = _MENU_STATIC_CACHE
        cx = w // 2
        comp.blit(s["title"], (cx - s["title"].get_width() // 2, 36))
        comp.blit(s["subtitle"], (cx - s["subtitle"].get_width() // 2, 104))
        comp.blit(s["diff_hint"],
                  (cx - s["diff_hint"].get_width() // 2, 142))

        picker = _DIFFICULTY_PICKER_CACHE[1]
        picker_x = cx - picker.get_width() // 2
        picker_y = 168
        comp.blit(picker, (picker_x, picker_y))

        card_w, card_h, gap = 230, 138, 22
        _DIFFICULTY_CARD_RECTS.clear()
        for i, key in enumerate(DIFFICULTY_ORDER):
            _DIFFICULTY_CARD_RECTS[key] = pygame.Rect(
                picker_x + i * (card_w + gap),
                picker_y + 12,
                card_w,
                card_h,
            )

        btn_w, btn_h = 300, 60
        btn_rect = pygame.Rect(cx - btn_w // 2,
                               picker_y + 12 + card_h + 22, btn_w, btn_h)
        _START_BUTTON_RECT = btn_rect

        comp.blit(s["hint"],
                  (cx - s["hint"].get_width() // 2,
                   btn_rect.bottom + 12))

        panel = _MENU_LEADERBOARD_CACHE[1]
        panel_x = cx - panel.get_width() // 2
        panel_y = btn_rect.bottom + 44
        if panel_y + panel.get_height() > h - 12:
            panel_y = h - panel.get_height() - 12
        comp.blit(panel, (panel_x, panel_y))
        comp.blit(s["header"],
                  (panel_x + (panel.get_width() - s["header"].get_width()) // 2,
                   panel_y + 14))

        _MENU_COMPOSITE = comp
        _MENU_COMPOSITE_SIG = composite_sig

    merge_sig = (id(track_snapshot), _MENU_COMPOSITE_SIG)
    if _MENU_MERGED_BASE is None or _MENU_MERGED_SIG != merge_sig:
        merged = track_snapshot.copy()
        merged.blit(_MENU_COMPOSITE, (0, 0))
        try:
            merged = merged.convert_alpha(win)
        except pygame.error:
            pass
        _MENU_MERGED_BASE = merged
        _MENU_MERGED_SIG = merge_sig

    win.blit(_MENU_MERGED_BASE, (0, 0))

    btn_rect = _START_BUTTON_RECT
    if _START_BTN_CACHE is None or _START_BTN_CACHE[0] != (btn_rect.w, btn_rect.h):
        _START_BTN_CACHE = (
            (btn_rect.w, btn_rect.h),
            _build_start_button(btn_rect.w, btn_rect.h, hovering=False),
            _build_start_button(btn_rect.w, btn_rect.h, hovering=True),
        )
    hovering = btn_rect.collidepoint(mouse_pos)
    btn_surf = _START_BTN_CACHE[2] if hovering else _START_BTN_CACHE[1]
    win.blit(btn_surf, (btn_rect.x, btn_rect.y))

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
