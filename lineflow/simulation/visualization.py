import pygame

class Viewpoint:

    def __init__(
        self,
        size=None,
        position=None,
        zoom=1,
    ):

        if size is None:
        	size = (1410, 1000)

        self.paper = pygame.Surface(size)

        if position is None:
            position = (0, 0)

        self._view = pygame.Vector3(position[0], position[1], zoom)

    def check_view_update(self):

        if pygame.key.get_pressed()[pygame.K_PLUS]:
            self._view.z += 0.1

        if pygame.key.get_pressed()[pygame.K_MINUS]:
            self._view.z -=0.1

        if pygame.key.get_pressed()[pygame.K_UP]:
            self._view.y += 10

        if pygame.key.get_pressed()[pygame.K_DOWN]:
            self._view.y -= 10

        if pygame.key.get_pressed()[pygame.K_LEFT]:
            self._view.x += 10

        if pygame.key.get_pressed()[pygame.K_RIGHT]:
            self._view.x -= 10

        if self._view.z < 0.1:
            self._view.z = 0.1

        if self._view.z > 5:
            self._view.z = 5

    def clear_paper(self):
        self.paper.fill('white')

    def _draw(self, screen):
        screen.blit(
            pygame.transform.smoothscale_by(self.paper, self._view.z),
            (self._view.x,self._view.y),
        )