import pygame

#dataclass?
class Window:
    size = (1280, 720)
    center = pygame.Vector2(size[0]/2, size[1]/2)


class View:
    def __init__(self,x=0,y=0,z=1):
        self.x = x
        self.y = y
        self.z = z
    @property
    def offset(self) -> pygame.Vector2:
        return pygame.Vector2(self.x, self.y)
#todo: Tobias pls improve instantiation
view = View()

#class attribute of VisuObject? or something else
visu_objects = []

class VisuObject:
    
    def __init__(self, position:pygame.Vector2) -> None:
        self.position = position
        visu_objects.append(self)
    
    def draw(self, surface) -> None:
        raise NotImplementedError()


class VisuBlock(VisuObject):
    height = 30
    width = 30
    color = "blue"
    
    @property
    def Rect(self) -> pygame.Rect:
        Rect = pygame.Rect(
            view.x + self.position.x - self.width/2,
            view.y + self.position.y - self.height/2,
            self.width,
            self.height
        )
        return Rect
    
    def draw(self, surface) -> None:
        pygame.draw.rect(
            surface,
            self.color,
            self.Rect
        )


class VisuLine(VisuObject):
    color = "gray"
    width = 10

    def __init__(self, position:pygame.Vector2, endpoint:pygame.Vector2) -> None:
        super().__init__(position=position)
        self.endpoint = endpoint

    def draw(self, surface) -> None:
        pygame.draw.line(
            surface,
            self.color,
            view.offset + self.position,
            view.offset + self.endpoint,
            width=self.width
        )


class Crosshair(VisuObject):
    height = 10
    width = 10
    color = "red"

    def draw(self, surface) -> None:
        pygame.draw.line(
            surface,
            self.color,
            self.position + (self.height,0),
            self.position - (self.height,0))
        pygame.draw.line(
            surface,
            self.color,
            self.position + (0,self.width),
            self.position - (0,self.width)
        )


def clear(surface) -> None:
    surface.fill("white")

def check_user_input(dt) -> bool:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return False
    keys = pygame.key.get_pressed()
    if keys[pygame.K_q]:
        view.z -= 3*view.z*dt
    if keys[pygame.K_e]:
        view.z += 3*view.z*dt
    if keys[pygame.K_w] or keys[pygame.K_UP]:
        view.y += 300*view.z*dt
    if keys[pygame.K_s] or keys[pygame.K_DOWN]:
        view.y -= 300*view.z*dt
    if keys[pygame.K_a] or keys[pygame.K_LEFT]:
        view.x += 300*view.z*dt
    if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
        view.x -= 300*view.z*dt
    view.z = max(0.5,min(10,view.z))
    return True

def draw_objects_of_type(type, surface):
    for obj in visu_objects:
        if isinstance(obj, type):
            obj.draw(surface)

def draw_scene(surface):
    clear(surface)
    draw_objects_of_type(VisuLine, surface)
    draw_objects_of_type(VisuBlock, surface)
    draw_objects_of_type(Crosshair, surface)

def run() -> None:
    pygame.init()
    screen = pygame.display.set_mode(Window.size)
    clock = pygame.time.Clock()
    dt = 0
    while check_user_input(dt):
        draw_scene(screen)
        pygame.display.flip()
        dt = clock.tick(60)/1000
    pygame.quit()


if __name__ == '__main__':
    for n in range(3):
        VisuBlock(pygame.Vector2(100*(n+1),100))
    VisuLine(pygame.Vector2(100,100),pygame.Vector2(200,100))
    Crosshair(Window.center)
    run()