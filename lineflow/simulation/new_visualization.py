import pygame

class Window:
    size = pygame.Vector2(1280, 720)
    center = pygame.Vector2(size.x/2, size.y/2)


class View:
    def __init__(self,x:float=0.0,y:float=0.0,z:float=1.0):
        self.x = x
        self.y = y
        self.z = z
    @property
    def offset(self) -> pygame.Vector2:
        return pygame.Vector2(self.x, self.y)

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
            Window.center.x + (view.x + self.position.x - self.width/2)/view.z,
            Window.center.y + (view.y + self.position.y - self.height/2)/view.z,
            self.width/view.z,
            self.height/view.z
        )
        return Rect
    
    def draw(self, surface:pygame.Surface, scale:float=1.0) -> None:
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

    def draw(self, surface:pygame.Surface, scale:float=1.0) -> None:
        pygame.draw.line(
            surface,
            self.color,
            Window.center + (view.offset + self.position)/view.z,
            Window.center + (view.offset + self.endpoint)/view.z,
            width=int(self.width/view.z)
        )


class Crosshair(VisuObject):
    height = 10
    width = 10
    color = "red"

    def draw(self, surface:pygame.Surface) -> None:
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


class MiniMap(VisuObject):
    scale = 0.1

    def __init__(self, position:pygame.Vector2):
        super().__init__(position=position)
        self.active = True

    def toggle(self) -> None:
        self.active = not self.active

    def draw_minimap(self) -> pygame.Surface:
        return minimap

    def draw(self, surface:pygame.Surface) -> None:
        surface.blit(self.draw_minimap(), self.poisition)
        pygame.draw.rect(
            surface,
            self.color,
            self.Rect
        )


def find_line_bounds() -> pygame.Vecotr2:
    x_positions = []
    y_positions = []
    for item in visu_objects:
        if not isinstance(item, (Crosshair, MiniMap)):
            x_positions.append(item.position.x)
            y_positions.append(item.position.y)
    line_bounds = dict(
        upper_left=pygame.Vector2(min(x_positions), min(y_positions)),
        lower_right=pygame.Vector2(max(x_positions), max(y_positions))
    )
    return line_bounds

def find_line_size(line_bounds=None) -> pygame.Vector2:
    if line_bounds is None:
        line_bounds = find_line_bounds()
    line_width = line_bounds['lower_right'].x - line_bounds['upper_left'].x
    line_height = line_bounds['lower_right'].y - line_bounds['upper_left'].y
    line_center = line_bounds['upper_left'] + (line_width/2,line_height/2)
    return line_width, line_height, line_center

def set_initial_view() -> View:
    line_width, line_height, line_center = find_line_size()
    x = -line_center.x
    y = -line_center.y
    x_scalar = line_width / (Window.size.x-100)
    y_scalar = line_height / (Window.size.y-100)
    scalar = max(x_scalar,y_scalar)
    if scalar < 1:
        z = 1
    else:
        z = round(scalar,1)
    return View(x,y,z)

def clear(surface:pygame.Surface) -> None:
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

def draw_objects_of_type(type, surface:pygame.Surface) -> None:
    for obj in visu_objects:
        if isinstance(obj, type):
            obj.draw(surface)

def draw_scene(surface:pygame.Surface) -> None:
    clear(surface)
    draw_objects_of_type(VisuLine, surface)
    draw_objects_of_type(VisuBlock, surface)
    draw_objects_of_type(Crosshair, surface)
    draw_objects_of_type(MiniMap, surface)

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
    view = set_initial_view()
    run()