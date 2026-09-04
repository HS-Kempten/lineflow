import pygame
import logging
from queue import Empty
from multiprocessing import Queue, Event



logger = logging.getLogger(__name__)

class ConnectionData:
    """Object for transfering data to Visualization
    ToDo: Remove redundant Methods"""

    def __init__(self, type:str, layer:int, **kwargs):
        self.type = type
        self.layer = layer
        for k, v in kwargs.items():
            self.__setattr__(k, v)

    def __repr__(self):
        rep = f"{self.type}("
        for n, k in enumerate(self.__dict__):
            if not k == "type":
                rep += f"{k}={self.__dict__[k]}"
                if n < len(self.__dict__)-1:
                    rep += f","
        rep += f")" 
        return rep

    def __iter__(self):
        for k in self.__dict__:
            yield k

    def __eq__(self, other):
        return self.name == other

    def __lt__(self, other):
        return self.layer < other.layer


def setup_communication_pair():
    child = Communication(Queue(), Queue())
    parent = Communication(child.queue_out,child.queue_in, child)
    return parent, child

class Communication:
    """
    To be imported by line.py setup 2 instances and give 1 to visualization_process as arg.
    or just import setup_communication_pair
    """

    def __init__(self, queue_in, queue_out,  child=None):
        self.data = None
        self.queue_in = queue_in
        self.queue_out = queue_out
        self.child = child

    def new_event(self, name):
        #only use before starting second process
        event = Event()
        self.__setattr__(name, event)
        if self.child is not None:
            self.child.__setattr__(name, event)

    def recieve(self):
        try:
            self.data = self.queue_in.get_nowait()
        except Empty:
            logger.warning(f"No data to read!")

    def recieve_all(self):
        while True:
            try:
                self.data = self.queue_in.get_nowait()
            except Empty:
                break

    def send(self, data):
        self.queue_out.put(data)


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
perm_visu_objects = []
temp_visu_objects = []


#Definition of Visualization specific Objects
class VisuObject:
    def __init__(self, position:pygame.Vector2) -> None:
        self.position = position
        perm_visu_objects.append(self)

    def draw(self, surface) -> None:
        raise NotImplementedError()


class VisuBlock(VisuObject):
    def __init__(self, position):
        super().__init__(position=position)
        self.height = 30
        self.width = 30
        self.radius = 8
        self.color = "blue"
    
    @property
    def Rect(self) -> pygame.Rect:
        Rect = pygame.Rect(
            Window.center.x + (view.x + self.position.x - self.width/2)/view.z,
            Window.center.y + (view.y + self.position.y - self.height/2)/view.z,
            self.width/view.z,
            self.height/view.z,
        )
        return Rect

    @property
    def hovered(self) -> bool:
        return self.Rect.collidepoint(pygame.mouse.get_pos())

    def renderBlock(self, surface) -> None:
        pygame.draw.rect(
            surface,
            self.color,
            self.Rect,
            border_radius = int(self.radius/view.z)
        )
    
    def draw(self, surface:pygame.Surface) -> None:
        self.renderBlock(surface)

    def draw_simple(self, surface, offset, scale):
        pygame.draw.circle(
            surface,
            self.color,
            offset + self.position*scale,
            int(self.height/2 * scale)
        )


class VisuLine(VisuObject):
    color = "gray"
    width = 10

    def __init__(self, position:pygame.Vector2, endpoint:pygame.Vector2) -> None:
        super().__init__(position=position)
        self.endpoint = endpoint

    @property
    def hovered(self) -> bool:
        #calculate via polytope
        return False

    def renderLine(self, surface) -> None:
        pygame.draw.line(
            surface,
            self.color,
            Window.center + (view.offset + self.position)/view.z,
            Window.center + (view.offset + self.endpoint)/view.z,
            width=int(self.width/view.z)
        )

    def draw(self, surface:pygame.Surface) -> None:
        self.renderLine(surface)

    def draw_simple(self, surface:pygame.Surface, offset:pygame.Vector2, scale:float) -> None:
        pygame.draw.line(
            surface,
            self.color,
            offset + self.position*scale,
            offset + self.endpoint*scale,
            width=int(self.width*scale)
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
    def __init__(self, size=None, position=None):
        self.name = "MiniMap"
        self.active = True
        self.scale = 0.5
        self.color = "red"
        self.border = pygame.Vector2(2, 2)
        self.margin = pygame.Vector2(10, 10)
        self.size = (pygame.Vector2(
                size[0]*self.scale,
                size[1]*self.scale
            ) + self.margin*2
        )
        self.offset = self.size/2 - size[2]*self.scale
        if position is None:
            position = pygame.Vector2(
            Window.size.x - self.size.x - self.border.x,
            self.border.y
        )
        self.minimap = pygame.Surface(self.size)
        super().__init__(position=position)

    @property
    def Rect(self) -> None:
        Rect = pygame.Rect(
            self.position - self.border,
            self.size + self.border*2
        )
        return Rect

    def toggle(self) -> None:
        self.active = not self.active

    def draw_simple_objects_of_type(self, type:VisuObject) -> None:
        for obj in temp_visu_objects:
            if isinstance(obj, type):
                obj.draw_simple(self.minimap, self.offset, self.scale)

    def render_minimap(self) -> pygame.Surface:
        clear(self.minimap)
        self.draw_simple_objects_of_type(VisuLine)
        self.draw_simple_objects_of_type(VisuBlock)
        return self.minimap

    def draw(self, surface:pygame.Surface) -> None:
        if self.active:
            pygame.draw.rect(surface, self.color, self.Rect)
            surface.blit(self.render_minimap(), self.position)


#Start of Simulation Equivalent Classes

class VisuEquivalent(VisuObject):
    def __init__(self, obj:ConnectionData):
        temp_visu_objects.append(self)
        self.name = obj.name
        self.position = obj.position
        self.color = "gray"

    def __eq__(self, other:str) -> bool:
        return self.name == other

    def update(self, obj:ConnectionData) -> None:
        self.position = obj.position


class VisuStation(VisuEquivalent):
    def __init__(self, obj:ConnectionData):
        super().__init__(obj=obj)
        self.mode = obj.mode
        self.on = obj.on
        self.height = 30
        self.width = 30
        self.radius = 8
        self.color_mapping = {
            "working": "green",
            "waiting": "yellow",
            "failing": "red",
        }

    @property
    def Rect(self) -> pygame.Rect:
        Rect = pygame.Rect(
            Window.center.x + (view.x + self.position.x - self.width/2)/view.z,
            Window.center.y + (view.y + self.position.y - self.height/2)/view.z,
            self.width/view.z,
            self.height/view.z,
        )
        return Rect

    @property
    def station_color(self) -> str:
        station_color = self.color_mapping[self.mode]
        if not self.on:
            station_color = self.color
        return station_color

    @property
    def hovered(self) -> bool:
        return self.Rect.collidepoint(pygame.mouse.get_pos())

    def update(self, obj:ConnectionData) -> None:
        super().update(obj=obj)
        self.mode = obj.mode
        self.on = obj.on

    def renderBlock(self, surface) -> None:
        pygame.draw.rect(
            surface,
            self.station_color,
            self.Rect,
            border_radius = int(max(1,self.radius/view.z))
        )

    def renderName(self, surface) -> None:
        font = pygame.font.SysFont(None, int(20/view.z))
        name_text = font.render(self.name, True, 'black')
        surface.blit(
            name_text,
            name_text.get_rect(
                center=Window.center + (view.offset + self.position + (0, -0.7*self.height))/view.z
            )
        )

    def draw(self, surface:pygame.Surface) -> None:
        self.renderBlock(surface)
        self.renderName(surface)

    def draw_simple(self, surface:pygame.Surface, offset:pygame.Vector2, scale:float) -> None:
        pygame.draw.circle(
            surface,
            self.color,
            offset + self.position*scale,
            int(self.height/2 * scale)
        )


class VisuSwitch(VisuStation):
    def __init__(self, obj:ConnectionData):
        super().__init__(obj=obj)
        self.pos_in = obj.pos_in_out[0]
        self.pos_out = obj.pos_in_out[1]
        self.connector_color = VisuConnector.color

    def update(self, obj:ConnectionData) -> None:
        super().update(obj=obj)
        self.pos_in = obj.pos_in_out[0]
        self.pos_out = obj.pos_in_out[1]

    def render_connections(self, surface:pygame.Surface) -> None:
        pygame.draw.circle(
            surface,
            connector_color,
            Window.center + (view.offset + self.position)/view.z,
            self.width/5/view.z
        )
        pygame.draw.lines(
            surface,
            connector_color,
            (
                Window.center + (view.offset + self.pos_in)/view.z,
                Window.center + (view.offset + self.position)/view.z,
                Window.center + (view.offset + self.pos_out)/view.z
            ),
            width=int(VisuConnector.width/view.z)
        )

    def draw(self, surface:pygame.Surface) -> None:
        super().draw(surface=surface)
        self.render_connections(surface)


class VisuConnector(VisuEquivalent):
    def __init__(self, obj:ConnectionData) -> None:
        super().__init__(obj=obj)
        self.endpoint = obj.endpoint
        self.width = 10

    @property
    def hovered(self) -> bool:
        #calculate via polytope
        return False

    def renderLine(self, surface:pygame.Surface) -> None:
        pygame.draw.line(
            surface,
            self.color,
            Window.center + (view.offset + self.position)/view.z,
            Window.center + (view.offset + self.endpoint)/view.z,
            width=int(self.width/view.z)
        )

    def draw(self, surface:pygame.Surface) -> None:
        self.renderLine(surface)

    def draw_simple(self, surface:pygame.Surface, offset:pygame.Vector2, scale:float) -> None:
        pygame.draw.line(
            surface,
            self.color,
            offset + self.position*scale,
            offset + self.endpoint*scale,
            width=int(self.width*scale)
        )


class VisuBuffer(VisuEquivalent):
    def __init__(self, obj:ConnectionData) -> None:
        super().__init__(obj=obj)
        self.capacity = obj.capacity

    def renderSlots(self, surface) -> None:
        length = self.endpoint/view.z-self.position/view.z
        snippet = length/(self.capacity+1)
        for n in range(self.capacity):
            pygame.draw.circle(
                surface,
                self.color,
                Window.center + (view.offset + self.position + snippet*(n+1))/view.z,
                int(self.width/view.z)
            )

    def draw(self, surface:pygame.Surface) -> None:
        super().draw(surface=surface)
        self.renderSlots(surface)


class VisuCarrier(VisuEquivalent):
    def __init__(self, obj:ConnectionData) -> None:
        super().__init__(obj=obj)
        self.fill = obj.fill
        self.color = "black"
        self.item_color = "orange"
        self.height = 10
        self.width = 30

    @property
    def Rect(self) -> pygame.Rect:
        Rect = pygame.Rect(
            Window.center.x + (view.x + self.position.x - self.width/2)/view.z,
            Window.center.y + (view.y + self.position.y - self.height/2)/view.z,
            self.width/view.z,
            self.height/view.z,
        )
        return Rect

    @property
    def hovered(self) -> bool:
        return self.Rect.collidepoint(pygame.mouse.get_pos())

    @property
    def Items(self) -> pygame.Rect:
        Items = self.Rect.inflate(-4/view.z, -4/view.z)
        Items.inflate_ip(-(self.width-4/view.z)*(1-self.fill)/view.z, 0)
        Items.move_ip(-(self.width-4/view.z)*(1-self.fill)/2/view.z, 0)
        return Items
    
    def renderBlock(self, surface) -> None:
        pygame.draw.rect(
            surface,
            self.color,
            self.Rect,
        )

    def renderItems(self, surface:pygame.Surface) -> None:
        pygame.draw.rect(
            surface,
            self.item_color,
            self.Items
        )

    def draw(self, surface:pygame.Surface) -> None:
        self.renderBlock(surface)
        self.renderItems(surface)

    def draw_simple(self, surface:pygame.Surface, offset:pygame.Vector2, scale:float):
        pygame.draw.circle(
            surface,
            self.item_color,
            offset + self.position*scale,
            int(self.width/3 * scale)
        )

#End of Simulation Equivalent Classes


object_mapping = {
    "station":VisuStation,
    "source":VisuStation,
    "sink":VisuStation,
    "switch":VisuSwitch,
    "sonnector":VisuConnector,
    "buffer":VisuBuffer,
    "carrier":VisuCarrier
}

def create_visu_object(obj) -> None:
    object_mapping[obj.type](obj)

def delete_visu_object(obj) -> None:
    temp_visu_objects.remove(obj)

def visu_heartbeat(data) -> None:
    remove_from_visu = []
    for visu_obj in temp_visu_objects:
        if visu_obj not in data:
            remove_from_visu.append(visu_obj)
        else:
            i = connection.data.index(visu_obj.name)
            visu_obj.update(data[i])
    for visu_obj in remove_from_visu:
        delete_visu_object(visu_obj)
    remove_from_visu = []
    for sim_obj in data:
        if sim_obj not in temp_visu_objects:
            create_visu_object(sim_obj)

def find_line_bounds() -> pygame.Vecotr2:
    x_positions = []
    y_positions = []
    for item in temp_visu_objects:
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
    return (line_width, line_height, line_center)

def set_initial_view(line_size=None) -> View:
    if line_size is None:
        line_width, line_height, line_center = find_line_size()
    else:
        line_width, line_height, line_center = line_size
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
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_m:
                minimap.toggle()
        elif event.type == pygame.MOUSEWHEEL:
            view.z += 5 * event.y * view.z * dt
    
    _mouse = pygame.mouse.get_pressed(num_buttons=3)
    mouse_rel = pygame.mouse.get_rel()
    if _mouse[0]:
        view.x += mouse_rel[0] * view.z
        view.y += mouse_rel[1] * view.z
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
    for obj in perm_visu_objects + temp_visu_objects:
        if isinstance(obj, type):
            obj.draw(surface)

def draw_scene(surface:pygame.Surface) -> None:
    clear(surface)
    draw_objects_of_type(VisuConnector, surface)
    draw_objects_of_type(VisuStation, surface)
    draw_objects_of_type(VisuCarrier, surface)
    draw_objects_of_type(Crosshair, surface)
    draw_objects_of_type(MiniMap, surface)

def run_visualization(connection:Communication) -> None:
    pygame.init()
    screen = pygame.display.set_mode(Window.size)
    clock = pygame.time.Clock()
    dt = 0
    initialized = False
    running = True
    while running:
        print(temp_visu_objects)
        if initialized:
            running = check_user_input(dt)
        connection.recieve_all()
        visu_heartbeat(connection.data)

#classes initialized here need to be in "global namespace"
        if not initialized and connection.data is not None:
            Crosshair(Window.center)
            line_size = find_line_size()
            minimap = MiniMap(find_line_size)
            view = set_initial_view(line_size=find_line_size)
            initialized = True


        draw_scene(screen)
        pygame.display.flip()
        dt = clock.tick(60)/1000
    pygame.quit()