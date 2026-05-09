"""Track bitmaps, grass mask, finish trigger."""
import pygame

from assets import PLAYFIELD_RECT


class Track:
    def __init__(self, surface, border_surface, border_mask,
                 finish_surface, finish_position, path):
        self.surface = surface
        self.border_surface = border_surface
        self.border_mask = border_mask
        self.finish_surface = finish_surface
        self.finish_position = finish_position
        self.finish_mask = pygame.mask.from_surface(finish_surface)

        self.boundary_points = path
        self.start_line = finish_position

        self.checkpoints = self._build_checkpoints(path)

    def _build_checkpoints(self, path):
        if not path:
            return []
        indices = [
            len(path) // 4,
            len(path) // 2,
            (3 * len(path)) // 4,
        ]
        return [path[i] for i in indices]

    def get_track_path(self):
        return list(self.boundary_points)

    def is_out_of_bounds(self, car):
        # Car x/y and masks stay in track-bitmap space; PLAYFIELD_* is draw-only.
        return car.check_collision(self.border_mask) is not None

    def at_finish_line(self, car):
        return car.check_collision(
            self.finish_mask, *self.finish_position
        )

    def draw(self, win):
        ox, oy = PLAYFIELD_RECT.topleft
        win.blit(self.surface, (ox, oy))
        win.blit(self.finish_surface,
                 (ox + self.finish_position[0], oy + self.finish_position[1]))
        win.blit(self.border_surface, (ox, oy))
