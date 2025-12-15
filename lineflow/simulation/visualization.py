import pygame
import sys

class Viewpoint:
    """
    A class to manage the viewpoint for rendering a 2D surface with zoom and pan capabilities.
    """

    def __init__(
        self,
        size=None,
        position=None,
        zoom=1,
    ):


        if size is None:
        	size = (1410, 1000)
        self.paper = pygame.Surface(size)


        self.screen = pygame.display.set_mode((1280, 720))

        if position is None:
            position = (0, 0)
        
        self._view = pygame.Vector3(position[0], position[1], zoom)

    def check_user_input(self):

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

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.teardown()

        self._view.z = max(self._view.z, 0.1)
        self._view.z = min(self._view.z, 5)

    def clear(self):
        self.screen.fill('white')
        self.paper.fill('white')

    def _draw(self):
        self.screen.blit(
            pygame.transform.smoothscale_by(self.paper, self._view.z),
            (self._view.x,self._view.y),
        )

    def teardown(self):
        pygame.quit()
        sys.exit()
