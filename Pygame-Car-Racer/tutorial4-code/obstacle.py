"""Obstacle and NitroPad classes - interactive elements on the track.

Uses Axis-Aligned Bounding Box (AABB) collision detection.
"""
import math
import random

import pygame


class Obstacle:
    """Static obstacle that decreases the car's speed on hit."""

    TYPES = {
        "cone": {"color": (255, 140, 30), "radius": 10, "penalty": 0.6},
        "barrel": {"color": (180, 60, 60), "radius": 13, "penalty": 0.4},
        "oil": {"color": (40, 40, 50), "radius": 16, "penalty": 0.3},
    }

    _RENDER_CACHE = {}

    def __init__(self, position, obstacle_type="cone"):
        if obstacle_type not in self.TYPES:
            obstacle_type = "cone"
        spec = self.TYPES[obstacle_type]
        self.position = position
        self.type = obstacle_type
        self.radius = spec["radius"]
        self.color = spec["color"]
        self.speed_penalty = spec["penalty"]
        self.active = True
        self._was_hitting = False

    @property
    def rect(self):
        x, y = self.position
        r = self.radius
        return pygame.Rect(x - r, y - r, r * 2, r * 2)

    def aabb_collides_with(self, car_rect):
        """AABB collision detection between this obstacle and a car rect."""
        return self.rect.colliderect(car_rect)

    def update_collision(self, car_rect):
        """Edge-triggered hit detection. Returns True only on the frame
        the car ENTERS the obstacle (so a car parked on top isn't hit
        every frame)."""
        if not self.active:
            self._was_hitting = False
            return False
        is_hitting = self.aabb_collides_with(car_rect)
        just_entered = is_hitting and not self._was_hitting
        self._was_hitting = is_hitting
        return just_entered

    def on_hit(self, car):
        """Apply speed penalty to the car. Returns True if a hit occurred."""
        if not self.active:
            return False
        if self.type == "oil":
            car.vel *= self.speed_penalty
            car.angle += random.uniform(-15, 15)
        else:
            car.vel *= self.speed_penalty
            self.active = False
        return True

    def _build_sprite(self):
        size = self.radius * 2 + 6
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        cx = cy = size // 2
        r = self.radius
        if self.type == "cone":
            pygame.draw.polygon(
                surf, self.color,
                [(cx, cy - r), (cx - r, cy + r), (cx + r, cy + r)],
            )
            pygame.draw.line(surf, (255, 255, 255),
                             (cx - r + 3, cy + 2),
                             (cx + r - 3, cy + 2), 2)
        elif self.type == "barrel":
            pygame.draw.circle(surf, self.color, (cx, cy), r)
            pygame.draw.circle(surf, (240, 220, 120), (cx, cy), r, 2)
            pygame.draw.line(surf, (240, 220, 120),
                             (cx - r + 2, cy),
                             (cx + r - 2, cy), 2)
        elif self.type == "oil":
            rect = pygame.Rect(cx - r - 1, cy - r - 1, r * 2 + 2, r * 2 + 2)
            pygame.draw.ellipse(surf, (*self.color, 220), rect)
            pygame.draw.ellipse(surf, (90, 90, 110, 200), rect, 1)
        return surf

    def render(self, win):
        if not self.active:
            return
        sprite = Obstacle._RENDER_CACHE.get(self.type)
        if sprite is None:
            sprite = self._build_sprite()
            Obstacle._RENDER_CACHE[self.type] = sprite
        x, y = self.position
        win.blit(sprite, (x - sprite.get_width() // 2,
                          y - sprite.get_height() // 2))


class NitroPad:
    """Boost pad that grants temporary nitro charge to the player."""

    def __init__(self, position, charge=2.0):
        self.position = position
        self.charge = charge
        self.radius = 18
        self.cooldown = 0
        self.cooldown_max = 180

    @property
    def rect(self):
        x, y = self.position
        r = self.radius
        return pygame.Rect(x - r, y - r, r * 2, r * 2)

    def aabb_collides_with(self, car_rect):
        if self.cooldown > 0:
            return False
        return self.rect.colliderect(car_rect)

    def on_hit(self, car):
        if self.cooldown > 0:
            return False
        car.add_nitro(self.charge)
        self.cooldown = self.cooldown_max
        return True

    def update(self):
        if self.cooldown > 0:
            self.cooldown -= 1

    _SPRITE_CACHE = {}

    @classmethod
    def _get_sprites(cls, radius):
        cached = cls._SPRITE_CACHE.get(radius)
        if cached is not None:
            return cached

        def build(outer, inner):
            size = radius * 4
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            cx = cy = size // 2
            pygame.draw.circle(surf, outer, (cx, cy), radius, 3)
            pygame.draw.polygon(
                surf, inner,
                [(cx, cy - radius + 5),
                 (cx - 6, cy + 2), (cx - 2, cy + 2),
                 (cx - 4, cy + radius - 5),
                 (cx + 6, cy - 2), (cx + 2, cy - 2)],
            )
            return surf

        ready = build((90, 220, 255), (220, 250, 255))
        cooldown = build((60, 80, 100), (120, 140, 160))

        glow_size = radius * 4
        glow = pygame.Surface((glow_size, glow_size), pygame.SRCALPHA)
        pygame.draw.circle(glow, (90, 220, 255, 255),
                           (glow_size // 2, glow_size // 2),
                           int(radius * 1.8))

        cached = (ready, cooldown, glow)
        cls._SPRITE_CACHE[radius] = cached
        return cached

    def render(self, win):
        x, y = self.position
        ready_sprite, cooldown_sprite, glow_sprite = self._get_sprites(
            self.radius)

        if self.cooldown <= 0:
            pulse = (math.sin(pygame.time.get_ticks() * 0.01) + 1) * 0.5
            alpha = int(60 + 60 * pulse)
            glow_sprite.set_alpha(alpha)
            gw = glow_sprite.get_width()
            win.blit(glow_sprite, (x - gw // 2, y - gw // 2))
            base = ready_sprite
        else:
            base = cooldown_sprite

        bw = base.get_width()
        win.blit(base, (x - bw // 2, y - bw // 2))


def spawn_obstacles(path, count, seed=None):
    """Dynamic obstacle spawning along the racing path (skips first/last)."""
    rng = random.Random(seed)
    obstacles = []
    if len(path) < 4:
        return obstacles
    valid_indices = list(range(2, len(path) - 1))
    rng.shuffle(valid_indices)
    types = list(Obstacle.TYPES.keys())
    for idx in valid_indices[:count]:
        x, y = path[idx]
        ox = x + rng.randint(-25, 25)
        oy = y + rng.randint(-25, 25)
        obstacles.append(Obstacle((ox, oy), rng.choice(types)))
    return obstacles
