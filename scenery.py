"""Grandstands along the **outer** edge of the circuit (reference-style crowd blocks).

Track bitmap uses transparent cut-outs over grass; placement uses a lawn flood-fill plus
PATH polygon probes so hairpin infield stays empty.
"""
from __future__ import annotations

import math
import random
from collections import deque
from typing import Tuple

import pygame

from assets import TRACK_SURFACE, WIDTH, track_to_screen
from settings import PATH

_PATH_CX = sum(p[0] for p in PATH) / len(PATH)
_PATH_CY = sum(p[1] for p in PATH) / len(PATH)

_hairpin_exclusion_rect: pygame.Rect | None = None
_lower_loop_exclusion_rect: pygame.Rect | None = None

_LAWN_GRID_STEP = 4
_OUTER_LAWN_ALPHA_MIN = 55
_outer_lawn_flood_cache: set[tuple[int, int]] | None = None
_spectator_surface_cache: pygame.Surface | None = None


def _point_in_path_interior(tx: float, ty: float) -> bool:
    verts = PATH
    n = len(verts)
    c = False
    j = n - 1
    for i in range(n):
        xi, yi = float(verts[i][0]), float(verts[i][1])
        xj, yj = float(verts[j][0]), float(verts[j][1])
        denom = yj - yi
        if denom == 0:
            intersect = False
        else:
            intersect = ((yi > ty) != (yj > ty)) and (
                tx < (xj - xi) * (ty - yi) / denom + xi
            )
        if intersect:
            c = not c
        j = i
    return c


def _get_hairpin_exclusion_rect() -> pygame.Rect | None:
    """Box over the grass pocket inside the bottom hairpin (PATH order is not spatial)."""
    global _hairpin_exclusion_rect
    if _hairpin_exclusion_rect is not None:
        return _hairpin_exclusion_rect
    if not PATH:
        _hairpin_exclusion_rect = pygame.Rect(0, 0, 0, 0)
        return None
    apex = max(PATH, key=lambda p: p[1])
    ax, ay = float(apex[0]), float(apex[1])
    w_box, h_box = 268, 235
    left = int(ax - w_box * 0.34)
    top = int(ay - h_box - 52)
    _hairpin_exclusion_rect = pygame.Rect(left, top, w_box, h_box)
    return _hairpin_exclusion_rect


def _get_lower_loop_exclusion_rect() -> pygame.Rect | None:
    """Box over the inner grass island of the lower U-turn."""
    global _lower_loop_exclusion_rect
    if _lower_loop_exclusion_rect is not None:
        return _lower_loop_exclusion_rect
    if len(PATH) < 10:
        _lower_loop_exclusion_rect = pygame.Rect(0, 0, 0, 0)
        return None

    # The lower loop is bounded by PATH[6:10] in the authored circuit. Keep
    # this rectangle conservative so exterior stands on the lower-left straight
    # still survive while the enclosed hairpin lawn stays empty.
    loop = PATH[6:10]
    min_x = min(p[0] for p in loop)
    max_x = max(p[0] for p in loop)
    min_y = min(p[1] for p in loop)
    max_y = max(p[1] for p in loop)
    left = int(min_x + (max_x - min_x) * 0.30)
    top = int(min_y + 18)
    width = int((max_x - min_x) * 0.70)
    height = int((max_y - min_y) + 54)
    _lower_loop_exclusion_rect = pygame.Rect(left, top, width, height)
    return _lower_loop_exclusion_rect


def _track_sample_bans_stand(x: float, y: float) -> bool:
    """Opaque asphalt/curb in the bitmap — not a valid stand (and kills on-track draws)."""
    ix, iy = int(round(x)), int(round(y))
    w, h = TRACK_SURFACE.get_size()
    if not (0 <= ix < w and 0 <= iy < h):
        return True
    c = TRACK_SURFACE.get_at((ix, iy))
    r, g, b = int(c[0]), int(c[1]), int(c[2])
    a = int(c[3]) if len(c) > 3 else 255
    if a < _OUTER_LAWN_ALPHA_MIN:
        return False
    if _looks_like_asphalt(r, g, b) or _looks_like_curb(r, g, b):
        return True
    return False


def _point_bans_grandstand(tx: float, ty: float) -> bool:
    if _point_in_path_interior(tx, ty):
        return True
    for ex in (_get_hairpin_exclusion_rect(), _get_lower_loop_exclusion_rect()):
        if ex is not None and ex.width > 0 and ex.collidepoint(tx, ty):
            return True
    if _track_sample_bans_stand(tx, ty):
        return True
    return False


def _stand_overlaps_infield(
    nt: Tuple[float, float],
    fg: Tuple[float, float],
    ft: Tuple[float, float],
    w_half: float,
) -> bool:
    """True if footprint hits infield geometry, the hairpin pocket, or paved track."""
    ntlo = (nt[0] - ft[0] * w_half, nt[1] - ft[1] * w_half)
    ntri = (nt[0] + ft[0] * w_half, nt[1] + ft[1] * w_half)
    fglo = (fg[0] - ft[0] * w_half, fg[1] - ft[1] * w_half)
    fgti = (fg[0] + ft[0] * w_half, fg[1] + ft[1] * w_half)
    lip = 5.5
    fn = (fg[0] - nt[0], fg[1] - nt[1])
    fl = math.hypot(fn[0], fn[1]) or 1.0
    fn = (fn[0] / fl * lip, fn[1] / fl * lip)
    roof_lo = (
        fglo[0] - ft[0] * w_half * 0.04 + fn[0],
        fglo[1] - ft[1] * w_half * 0.04 + fn[1],
    )
    roof_ro = (
        fgti[0] + ft[0] * w_half * 0.04 + fn[0],
        fgti[1] + ft[1] * w_half * 0.04 + fn[1],
    )
    roof_li = (roof_lo[0] + fn[0] * 1.15, roof_lo[1] + fn[1] * 1.15)
    roof_ri = (roof_ro[0] + fn[0] * 1.15, roof_ro[1] + fn[1] * 1.15)

    for x, y in (
        nt,
        fg,
        ntlo,
        ntri,
        fglo,
        fgti,
        roof_lo,
        roof_ro,
        roof_li,
        roof_ri,
    ):
        if _point_bans_grandstand(x, y):
            return True

    for u in (0.12, 0.35, 0.55, 0.78):
        for v in (0.1, 0.35, 0.65, 0.9):
            bl = (
                ntlo[0] + (fglo[0] - ntlo[0]) * u,
                ntlo[1] + (fglo[1] - ntlo[1]) * u,
            )
            br = (
                ntri[0] + (fgti[0] - ntri[0]) * u,
                ntri[1] + (fgti[1] - ntri[1]) * u,
            )
            px = bl[0] + (br[0] - bl[0]) * v
            py = bl[1] + (br[1] - bl[1]) * v
            if _point_bans_grandstand(px, py):
                return True
    return False


def _outfield_normal_sign(px: float, py: float, nx: float, ny: float) -> int:
    """+1 / -1 so moving from the lane sample along ``sign * normal`` leaves the infield."""
    probe = 42.0
    inside_p = _point_in_path_interior(px + nx * probe, py + ny * probe)
    inside_m = _point_in_path_interior(px - nx * probe, py - ny * probe)
    if inside_p and not inside_m:
        return -1
    if inside_m and not inside_p:
        return 1
    rx, ry = px - _PATH_CX, py - _PATH_CY
    return 1 if nx * rx + ny * ry >= 0 else -1


def _looks_like_asphalt(r: int, g: int, b: int) -> bool:
    m = max(r, g, b)
    if m < 52:
        return False
    if abs(r - g) < 44 and abs(r - b) < 44 and abs(g - b) < 44:
        return m > 58
    return False


def _looks_like_curb(r: int, g: int, b: int) -> bool:
    if r > 115 and g < 105 and b < 105 and r > g + 25:
        return True
    if r > 195 and g > 195 and b > 195:
        if max(r, g, b) - min(r, g, b) < 55:
            return True
    return False


def _is_green_grass(r: int, g: int, b: int) -> bool:
    if _looks_like_curb(r, g, b) or _looks_like_asphalt(r, g, b):
        return False
    if g < 75:
        return False
    if g >= r + 20 and g >= b + 16:
        return True
    if g >= r + 14 and g >= b + 12 and g > 95:
        return True
    return False


def _cell_is_lawn(ci: int, cj: int, w: int, h: int, step: int) -> bool:
    x0, y0 = ci * step, cj * step
    x1 = min(w, x0 + step)
    y1 = min(h, y0 + step)
    if x1 <= x0 or y1 <= y0:
        return False
    pts = (
        (x0, y0),
        (x1 - 1, y0),
        (x0, y1 - 1),
        (x1 - 1, y1 - 1),
        ((x0 + x1 - 1) // 2, (y0 + y1 - 1) // 2),
    )
    lawn = 0
    road = 0
    n = 0
    for sx, sy in pts:
        if not (0 <= sx < w and 0 <= sy < h):
            continue
        n += 1
        c = TRACK_SURFACE.get_at((sx, sy))
        r, g, b = int(c[0]), int(c[1]), int(c[2])
        a = int(c[3]) if len(c) > 3 else 255
        if a < _OUTER_LAWN_ALPHA_MIN:
            lawn += 1
        elif _looks_like_asphalt(r, g, b) or _looks_like_curb(r, g, b):
            road += 1
        elif _is_green_grass(r, g, b):
            lawn += 1
        elif a >= 200 and r > 200 and g > 200 and b > 200:
            lawn += 1
    if n == 0:
        return False
    if road > (n + 1) // 2:
        return False
    return lawn >= (n * 2 + 2) // 3


def _cell_touches_transparent_edge(ci: int, cj: int, w: int, h: int, step: int) -> bool:
    x0, y0 = ci * step, cj * step
    x1 = min(w, x0 + step)
    y1 = min(h, y0 + step)
    pad = 1
    for sy in range(max(0, y0 - pad), min(h, y1 + pad)):
        for sx in range(max(0, x0 - pad), min(w, x1 + pad)):
            c = TRACK_SURFACE.get_at((sx, sy))
            a = int(c[3]) if len(c) > 3 else 255
            if a < _OUTER_LAWN_ALPHA_MIN:
                return True
    return False


def _compute_outer_lawn_cells() -> set[tuple[int, int]]:
    w, h = TRACK_SURFACE.get_size()
    step = _LAWN_GRID_STEP
    cw = (w + step - 1) // step
    ch = (h + step - 1) // step

    def walkable(ci: int, cj: int) -> bool:
        return _cell_is_lawn(ci, cj, w, h, step)

    q: deque[tuple[int, int]] = deque()
    seen: set[tuple[int, int]] = set()
    for ci in range(cw):
        for cj in range(ch):
            if not walkable(ci, cj):
                continue
            edge = ci == 0 or cj == 0 or ci == cw - 1 or cj == ch - 1
            if not edge and not _cell_touches_transparent_edge(ci, cj, w, h, step):
                continue
            if (ci, cj) not in seen:
                seen.add((ci, cj))
                q.append((ci, cj))

    while q:
        ci, cj = q.popleft()
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ni, nj = ci + di, cj + dj
            if not (0 <= ni < cw and 0 <= nj < ch):
                continue
            if (ni, nj) in seen:
                continue
            if not walkable(ni, nj):
                continue
            seen.add((ni, nj))
            q.append((ni, nj))

    return seen


def _get_outer_lawn_cells() -> set[tuple[int, int]]:
    global _outer_lawn_flood_cache
    if _outer_lawn_flood_cache is None:
        _outer_lawn_flood_cache = _compute_outer_lawn_cells()
    return _outer_lawn_flood_cache


def _is_reachable_outer_lawn(tx: float, ty: float) -> bool:
    w, h = TRACK_SURFACE.get_size()
    step = _LAWN_GRID_STEP
    cw = (w + step - 1) // step
    ch = (h + step - 1) // step
    ci = int(tx) // step
    cj = int(ty) // step
    ci = max(0, min(cw - 1, ci))
    cj = max(0, min(ch - 1, cj))
    return (ci, cj) in _get_outer_lawn_cells()


def _pixel_ok(r: int, g: int, b: int, a: int) -> bool:
    if a < 28:
        return True
    return _is_green_grass(r, g, b)


def _grass_cluster_ok(tx: float, ty: float) -> bool:
    ix, iy = int(round(tx)), int(round(ty))
    w, h = TRACK_SURFACE.get_size()
    for ox, oy in ((0, 0), (-5, 0), (5, 0), (0, -4), (0, 4), (-4, -4), (4, -4)):
        sx, sy = ix + ox, iy + oy
        if not (0 <= sx < w and 0 <= sy < h):
            return False
        c = TRACK_SURFACE.get_at((sx, sy))
        r, g, b = int(c[0]), int(c[1]), int(c[2])
        a = int(c[3]) if len(c) > 3 else 255
        if not _pixel_ok(r, g, b, a):
            return False
    return True


def _segment_grass_offset(
    mx: float, my: float, nx: float, ny: float, sign: int,
) -> float | None:
    for dist in range(88, 260, 5):
        gx = mx + nx * dist * sign
        gy = my + ny * dist * sign
        if not _grass_cluster_ok(gx, gy):
            continue
        if not _is_reachable_outer_lawn(gx, gy):
            continue
        return float(dist)
    return None


def _clear_sidebar(sx: float, sy: float) -> bool:
    if sx > WIDTH - 200:
        return False
    if sy < 8:
        return False
    return True


def _scr(x: float, y: float) -> tuple[int, int]:
    a, b = track_to_screen(x, y)
    return int(round(a)), int(round(b))


def _draw_track_rect(
    win: pygame.Surface,
    rect: pygame.Rect,
    color: Tuple[int, ...],
    width: int = 0,
) -> None:
    sx, sy = track_to_screen(rect.x, rect.y)
    pygame.draw.rect(
        win,
        color,
        pygame.Rect(int(sx), int(sy), rect.width, rect.height),
        width,
    )


def _lerp_point(
    a: Tuple[float, float],
    b: Tuple[float, float],
    t: float,
) -> Tuple[float, float]:
    return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t


# F1-style spectator mass (reference thumbnail palette).
_CROWD_PALETTE = (
    (230, 90, 120), (255, 140, 70), (255, 220, 60), (90, 200, 255),
    (200, 200, 240), (255, 255, 255), (120, 255, 160), (180, 100, 255),
    (240, 240, 60), (255, 180, 200), (100, 180, 255),
)


def _draw_grandstand_face(
    win: pygame.Surface,
    ntl: Tuple[float, float],
    ntr: Tuple[float, float],
    fgl: Tuple[float, float],
    fgr: Tuple[float, float],
    seed: int,
) -> None:
    """Crowd pixels on the stand front + concrete tiers (track-space → screen)."""
    rng = random.Random(seed)
    scr_poly = [_scr(*ntl), _scr(*ntr), _scr(*fgr), _scr(*fgl)]
    shadow_poly = [(x + 3, y + 4) for x, y in scr_poly]
    pygame.draw.polygon(win, (5, 8, 10, 72), shadow_poly)
    pygame.draw.polygon(win, (60, 62, 66), scr_poly)
    pygame.draw.polygon(win, (20, 22, 26), scr_poly, 1)

    n_rows = max(10, int(
        math.hypot(fgl[0] - ntl[0], fgl[1] - ntl[1]) / 3.8,
    ))
    for ri in range(n_rows):
        u = (ri + 0.45) / (n_rows + 1)
        bl = _lerp_point(ntl, fgl, u)
        br = _lerp_point(ntr, fgr, u)
        row_len = math.hypot(br[0] - bl[0], br[1] - bl[1])
        steps = max(12, int(row_len / 2.4))
        pygame.draw.line(win, (102, 105, 108), _scr(*bl), _scr(*br), 2)
        if ri % 2 == 0:
            pygame.draw.line(win, (42, 44, 48), _scr(*bl), _scr(*br), 1)
        for s in range(steps):
            e0, e1 = s / steps, (s + 1) / steps
            x0 = bl[0] + (br[0] - bl[0]) * e0
            y0 = bl[1] + (br[1] - bl[1]) * e0
            x1 = bl[0] + (br[0] - bl[0]) * e1
            y1 = bl[1] + (br[1] - bl[1]) * e1
            if s % 13 in (0, 1):
                col = (166, 168, 166)
            elif ri < n_rows // 6:
                col = (
                    46 + rng.randint(0, 16),
                    48 + rng.randint(0, 16),
                    58 + rng.randint(0, 18),
                )
            else:
                col = rng.choice(_CROWD_PALETTE)
                if rng.random() < 0.28:
                    col = tuple(max(0, c - rng.randint(35, 85)) for c in col)
            pygame.draw.line(win, col, _scr(x0, y0), _scr(x1, y1), 2)

    for aisle_t in (0.18, 0.38, 0.62, 0.82):
        near = _lerp_point(ntl, ntr, aisle_t)
        far = _lerp_point(fgl, fgr, aisle_t)
        pygame.draw.line(win, (178, 180, 176), _scr(*near), _scr(*far), 2)
        pygame.draw.line(win, (35, 37, 40), _scr(*near), _scr(*far), 1)

    pygame.draw.line(win, (200, 204, 198), _scr(*ntl), _scr(*ntr), 2)
    pygame.draw.line(win, (24, 28, 32), _scr(*fgl), _scr(*fgr), 2)


def _draw_grandstand_cell(
    win: pygame.Surface,
    nt: Tuple[float, float],
    fg: Tuple[float, float],
    ft: Tuple[float, float],
    w_half: float,
    seed: int,
) -> None:
    lip = 5.5
    fn = (fg[0] - nt[0], fg[1] - nt[1])
    fl = math.hypot(fn[0], fn[1]) or 1.0
    fn = (fn[0] / fl * lip, fn[1] / fl * lip)

    ntlo = (nt[0] - ft[0] * w_half, nt[1] - ft[1] * w_half)
    ntri = (nt[0] + ft[0] * w_half, nt[1] + ft[1] * w_half)
    fglo = (fg[0] - ft[0] * w_half, fg[1] - ft[1] * w_half)
    fgti = (fg[0] + ft[0] * w_half, fg[1] + ft[1] * w_half)

    apron = 5.0
    apron_lo = (ntlo[0] - fn[0] * apron, ntlo[1] - fn[1] * apron)
    apron_hi = (ntri[0] - fn[0] * apron, ntri[1] - fn[1] * apron)
    pygame.draw.line(win, (190, 192, 188), _scr(*apron_lo), _scr(*apron_hi), 3)
    pygame.draw.line(win, (42, 48, 52), _scr(*apron_lo), _scr(*apron_hi), 1)

    _draw_grandstand_face(win, ntlo, ntri, fglo, fgti, seed)

    roof_lo = (
        fglo[0] - ft[0] * w_half * 0.04 + fn[0],
        fglo[1] - ft[1] * w_half * 0.04 + fn[1],
    )
    roof_ro = (
        fgti[0] + ft[0] * w_half * 0.04 + fn[0],
        fgti[1] + ft[1] * w_half * 0.04 + fn[1],
    )
    roof_li = (
        roof_lo[0] + fn[0] * 1.15,
        roof_lo[1] + fn[1] * 1.15,
    )
    roof_ri = (
        roof_ro[0] + fn[0] * 1.15,
        roof_ro[1] + fn[1] * 1.15,
    )
    pygame.draw.polygon(
        win,
        (126, 36, 42),
        [_scr(*roof_lo), _scr(*roof_ro), _scr(*roof_ri), _scr(*roof_li)],
    )
    roof_mid_l = _lerp_point(roof_lo, roof_li, 0.46)
    roof_mid_r = _lerp_point(roof_ro, roof_ri, 0.46)
    pygame.draw.line(win, (182, 62, 66), _scr(*roof_mid_l), _scr(*roof_mid_r), 2)
    pygame.draw.polygon(
        win,
        (80, 24, 30),
        [_scr(*roof_lo), _scr(*roof_ro), _scr(*roof_ri), _scr(*roof_li)],
        1,
    )
    for t in (0.08, 0.26, 0.44, 0.62, 0.80, 0.96):
        base = _lerp_point(fglo, fgti, t)
        tip = _lerp_point(roof_li, roof_ri, t)
        pygame.draw.line(win, (86, 88, 90), _scr(*base), _scr(*tip), 2)


def _draw_sponsor_boards(
    win: pygame.Surface,
    x: float,
    y0: float,
    y1: float,
    seed: int,
) -> None:
    rng = random.Random(seed)
    colors = (
        (230, 45, 58), (245, 245, 238), (40, 48, 58),
        (80, 190, 235), (255, 204, 80), (40, 190, 120),
    )
    y = y0
    while y < y1 - 8:
        h = rng.randint(18, 30)
        rect = pygame.Rect(int(x), int(y), 14, min(h, int(y1 - y)))
        col = colors[(int(y * 7) + seed) % len(colors)]
        _draw_track_rect(win, rect, col)
        _draw_track_rect(win, rect, (18, 20, 24), 1)
        stripe_y = rect.y + rect.height // 2
        pygame.draw.line(
            win,
            tuple(max(0, c - 55) for c in col),
            _scr(rect.x + 2, stripe_y),
            _scr(rect.x + rect.width - 2, stripe_y),
            1,
        )
        hi = pygame.Rect(rect.x + 2, rect.y + 2, rect.width - 4, 2)
        _draw_track_rect(win, hi, (255, 255, 255, 150))
        y += h + rng.randint(8, 15)


def _draw_east_vip_box(
    win: pygame.Surface,
    x: float,
    y: float,
    w: float,
    h: float,
    seed: int,
) -> None:
    rng = random.Random(seed)
    rect = pygame.Rect(int(x), int(y), int(w), int(h))
    _draw_track_rect(win, rect.move(3, 4), (0, 0, 0, 65))
    _draw_track_rect(win, rect, (36, 42, 50))
    _draw_track_rect(win, rect, (10, 12, 16), 1)
    glass = pygame.Rect(rect.x + 5, rect.y + 5, rect.width - 10, rect.height - 14)
    _draw_track_rect(win, glass, (88, 138, 160, 190))
    for gx in range(glass.x + 7, glass.right - 4, 18):
        pygame.draw.line(win, (190, 220, 230), _scr(gx, glass.y + 1),
                         _scr(gx - 10, glass.bottom - 2), 1)
    for _ in range(9):
        px = rng.randint(glass.x + 6, glass.right - 7)
        py = rng.randint(glass.y + 7, glass.bottom - 7)
        col = rng.choice(_CROWD_PALETTE)
        pygame.draw.circle(win, col, _scr(px, py), 2)
    roof = [
        (rect.x - 4, rect.y - 5),
        (rect.right + 6, rect.y - 5),
        (rect.right + 1, rect.y + 3),
        (rect.x - 7, rect.y + 3),
    ]
    pygame.draw.polygon(win, (205, 42, 52), [_scr(*p) for p in roof])
    pygame.draw.polygon(win, (80, 20, 24), [_scr(*p) for p in roof], 1)


def _draw_east_light_tower(win: pygame.Surface, x: float, y: float) -> None:
    pygame.draw.line(win, (34, 38, 42), _scr(x, y), _scr(x, y + 96), 3)
    pygame.draw.line(win, (118, 124, 126), _scr(x - 2, y), _scr(x - 2, y + 96), 1)
    for k in range(0, 84, 16):
        pygame.draw.line(win, (82, 88, 92), _scr(x - 10, y + k + 10),
                         _scr(x + 10, y + k + 22), 1)
        pygame.draw.line(win, (82, 88, 92), _scr(x + 10, y + k + 10),
                         _scr(x - 10, y + k + 22), 1)
    head = [(x - 23, y - 9), (x + 23, y - 9), (x + 19, y + 8), (x - 19, y + 8)]
    pygame.draw.polygon(win, (24, 28, 32), [_scr(*p) for p in head])
    for lx in (-13, -4, 5, 14):
        pygame.draw.circle(win, (255, 240, 160), _scr(x + lx, y), 3)


def _draw_east_flags(
    win: pygame.Surface,
    x: float,
    y0: float,
    y1: float,
    seed: int,
) -> None:
    rng = random.Random(seed)
    colors = ((230, 45, 58), (255, 255, 255), (255, 206, 64),
              (70, 190, 240), (40, 190, 120))
    y = y0
    while y < y1:
        pole_h = rng.randint(20, 28)
        pygame.draw.line(win, (230, 232, 224), _scr(x, y), _scr(x, y + pole_h), 1)
        col = colors[(int(y) + seed) % len(colors)]
        flag = [(x, y + 2), (x + 15, y + 5), (x, y + 11)]
        pygame.draw.polygon(win, col, [_scr(*p) for p in flag])
        pygame.draw.polygon(win, (30, 34, 36), [_scr(*p) for p in flag], 1)
        y += rng.randint(38, 54)


def _draw_east_grandstand(win: pygame.Surface) -> None:
    """Long fixed stand on the east side where the automatic sampler is sparse."""
    ft = (0.0, 1.0)
    # Track-space coordinates intentionally extend a little beyond the track
    # bitmap; the full window grass continues there before the HUD widgets.
    for y0, y1 in ((104, 432), (456, 824)):
        lane = pygame.Rect(872, y0, 34, y1 - y0)
        _draw_track_rect(win, lane.move(4, 5), (0, 0, 0, 55))
        _draw_track_rect(win, lane, (62, 68, 68))
        _draw_track_rect(win, lane.inflate(-8, 0), (118, 124, 116))
        _draw_track_rect(win, pygame.Rect(876, y0 + 7, 7, y1 - y0 - 14),
                         (196, 198, 188))
        for y in range(y0 + 14, y1, 30):
            pygame.draw.line(win, (190, 196, 188), _scr(889, y),
                             _scr(889, y + 12), 1)
        _draw_sponsor_boards(win, 854, y0 + 14, y1 - 10, y0 + y1)

    sections = (
        ((912.0, 190.0), (958.0, 190.0), 86.0, 7001),
        ((914.0, 318.0), (966.0, 318.0), 94.0, 7002),
        ((912.0, 540.0), (966.0, 540.0), 102.0, 7003),
        ((914.0, 700.0), (970.0, 700.0), 98.0, 7004),
    )
    for nt, fg, half_len, seed in sections:
        _draw_grandstand_cell(win, nt, fg, ft, half_len, seed)

    for x, y, w, h, seed in (
        (930, 82, 74, 34, 7101),
        (936, 415, 82, 36, 7102),
        (936, 824, 78, 34, 7103),
    ):
        _draw_east_vip_box(win, x, y, w, h, seed)

    for x, y in ((1006, 142), (1012, 494), (1008, 764)):
        _draw_east_light_tower(win, x, y)

    _draw_east_flags(win, 905, 118, 420, 7301)
    _draw_east_flags(win, 906, 470, 802, 7302)

    fence_x = 895.0
    for y0, y1 in ((110.0, 430.0), (455.0, 805.0)):
        top = _scr(fence_x, y0)
        bottom = _scr(fence_x, y1)
        pygame.draw.line(win, (218, 222, 218), top, bottom, 2)
        pygame.draw.line(win, (30, 36, 40), (top[0] + 2, top[1]),
                         (bottom[0] + 2, bottom[1]), 1)
        for y in range(int(y0), int(y1), 28):
            p0 = _scr(fence_x - 3, y)
            p1 = _scr(fence_x + 7, y + 11)
            pygame.draw.line(win, (150, 156, 154), p0, p1, 1)


def _draw_spectator_scenery_to(win: pygame.Surface) -> None:
    _get_outer_lawn_cells()
    path = PATH
    n = len(path)
    if n < 3:
        return

    stride = 30.0

    for i in range(n):
        ax, ay = float(path[i][0]), float(path[i][1])
        bx, by = float(path[(i + 1) % n][0]), float(path[(i + 1) % n][1])
        dx, dy = bx - ax, by - ay
        seg_len = math.hypot(dx, dy)
        if seg_len < 10.0:
            continue

        tx, ty = dx / seg_len, dy / seg_len
        nx, ny = -ty, tx

        num = max(1, int(seg_len / stride))
        w_half = (seg_len / num) * 0.46
        depth = 14.0 + min(10.0, seg_len * 0.042)

        for k in range(num):
            t = (k + 0.5) / num
            px = ax + dx * t
            py = ay + dy * t
            sign = _outfield_normal_sign(px, py, nx, ny)
            off = _segment_grass_offset(px, py, nx, ny, sign)
            if off is None:
                continue
            cx = px + nx * off * sign
            cy = py + ny * off * sign
            if _point_bans_grandstand(cx, cy):
                continue
            if not _is_reachable_outer_lawn(cx, cy):
                continue
            if not _grass_cluster_ok(cx, cy):
                continue
            if cx > 830.0:
                continue
            sx, sy = track_to_screen(cx, cy)
            if not _clear_sidebar(sx, sy):
                continue

            fn = (nx * sign, ny * sign)
            nt = (cx - fn[0] * depth * 0.48, cy - fn[1] * depth * 0.48)
            fg = (cx + fn[0] * depth * 0.55, cy + fn[1] * depth * 0.55)

            if _stand_overlaps_infield(nt, fg, (tx, ty), w_half):
                continue

            seed = (i * 193 + k * 97 + sign * 401) & 0xFFFFFFF
            _draw_grandstand_cell(win, nt, fg, (tx, ty), w_half, seed)

    _draw_east_grandstand(win)


def draw_spectator_scenery(win: pygame.Surface) -> None:
    global _spectator_surface_cache
    if (_spectator_surface_cache is None
            or _spectator_surface_cache.get_size() != win.get_size()):
        _spectator_surface_cache = pygame.Surface(win.get_size(),
                                                  pygame.SRCALPHA)
        _draw_spectator_scenery_to(_spectator_surface_cache)
    win.blit(_spectator_surface_cache, (0, 0))
