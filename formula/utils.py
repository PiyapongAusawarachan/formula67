import pygame


def scale_image(img, factor):
    size = round(img.get_width() * factor), round(img.get_height() * factor)
    return pygame.transform.scale(img, size)


def blit_rotate_center(win, image, top_left, angle):
    rotated_image = pygame.transform.rotate(image, angle)
    new_rect = rotated_image.get_rect(
        center=image.get_rect(topleft=top_left).center)
    win.blit(rotated_image, new_rect.topleft)


def render_text_with_shadow(font, text, color=(240, 240, 245),
                            shadow_color=(0, 0, 0), offset=2):
    """Render text with a soft drop shadow for better readability."""
    base = font.render(text, True, color)
    shadow = font.render(text, True, shadow_color)
    surface = pygame.Surface(
        (base.get_width() + offset, base.get_height() + offset),
        pygame.SRCALPHA,
    )
    shadow.set_alpha(160)
    surface.blit(shadow, (offset, offset))
    surface.blit(base, (0, 0))
    return surface


def blit_text_center(win, font, text):
    """Centered modal-style banner with dimmed background and glowing text."""
    overlay = pygame.Surface(win.get_size(), pygame.SRCALPHA)
    overlay.fill((5, 8, 20, 170))
    win.blit(overlay, (0, 0))

    render = render_text_with_shadow(font, text, color=(255, 230, 120),
                                     shadow_color=(0, 0, 0), offset=3)

    pad_x, pad_y = 40, 24
    box_w = render.get_width() + pad_x * 2
    box_h = render.get_height() + pad_y * 2
    box_x = win.get_width() // 2 - box_w // 2
    box_y = win.get_height() // 2 - box_h // 2

    panel = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
    pygame.draw.rect(panel, (18, 22, 40, 230), panel.get_rect(),
                     border_radius=18)
    pygame.draw.rect(panel, (255, 210, 90, 220), panel.get_rect(),
                     width=3, border_radius=18)
    win.blit(panel, (box_x, box_y))

    win.blit(render, (win.get_width() / 2 - render.get_width() / 2,
                      win.get_height() / 2 - render.get_height() / 2))


def draw_rounded_panel(win, rect, fill=(15, 18, 32, 200),
                       border=(90, 200, 255, 220), radius=14, width=2):
    """Draw a translucent rounded panel with a colored border."""
    panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(panel, fill, panel.get_rect(), border_radius=radius)
    pygame.draw.rect(panel, border, panel.get_rect(),
                     width=width, border_radius=radius)
    win.blit(panel, (rect.x, rect.y))


_GRADIENT_CACHE = {}


def _get_gradient_strip(width, height, fg, radius):
    """Return a cached full-width rounded gradient strip."""
    key = (width, height, fg, radius)
    cached = _GRADIENT_CACHE.get(key)
    if cached is not None:
        return cached
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    for i in range(width):
        t = i / max(1, width - 1)
        r = int(fg[0] * (1 - t) + 255 * t)
        g = int(fg[1] * (1 - t) + 180 * t)
        b = int(fg[2] * (1 - t) + 80 * t)
        pygame.draw.line(surf, (r, g, b, 240), (i, 0), (i, height))
    mask = pygame.Surface((width, height), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(),
                     border_radius=radius)
    surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    _GRADIENT_CACHE[key] = surf
    return surf


def draw_progress_bar(win, rect, value, max_value,
                      fg=(80, 220, 255), bg=(40, 50, 70),
                      border=(200, 220, 255), radius=6):
    """Draw a rounded progress bar (e.g. speedometer). Uses a cached
    pre-rendered gradient strip — only the visible portion is blitted."""
    pct = max(0.0, min(1.0, value / max_value if max_value else 0))

    bg_key = ("bg", rect.width, rect.height, bg, radius)
    bg_surf = _GRADIENT_CACHE.get(bg_key)
    if bg_surf is None:
        bg_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(bg_surf, (*bg, 220), bg_surf.get_rect(),
                         border_radius=radius)
        _GRADIENT_CACHE[bg_key] = bg_surf
    win.blit(bg_surf, (rect.x, rect.y))

    fill_w = int(rect.width * pct)
    if fill_w > 0:
        strip = _get_gradient_strip(rect.width, rect.height, fg, radius)
        win.blit(strip, (rect.x, rect.y),
                 area=pygame.Rect(0, 0, fill_w, rect.height))

    pygame.draw.rect(win, border, rect, width=1, border_radius=radius)


_VIGNETTE_CACHE = {}


def draw_vignette(win):
    """Soft dark vignette around the edges. Cached per window size."""
    size = win.get_size()
    vignette = _VIGNETTE_CACHE.get(size)
    if vignette is None:
        w, h = size
        vignette = pygame.Surface((w, h), pygame.SRCALPHA)
        max_alpha = 110
        steps = 60
        for i in range(steps):
            alpha = int(max_alpha * (i / steps) ** 2)
            pygame.draw.rect(
                vignette, (0, 0, 0, alpha),
                pygame.Rect(i, i, w - i * 2, h - i * 2),
                width=1,
            )
        _VIGNETTE_CACHE[size] = vignette
    win.blit(vignette, (0, 0))
