"""Track class - handles environment, boundaries, and checkpoints."""
import pygame


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
        return car.check_collision(self.border_mask) is not None

    def at_finish_line(self, car):
        return car.check_collision(
            self.finish_mask, *self.finish_position
        )

    def draw(self, win):
        win.blit(self.surface, (0, 0))
        win.blit(self.finish_surface, self.finish_position)
        win.blit(self.border_surface, (0, 0))
