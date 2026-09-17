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
        self.new_data = False

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
                self.new_data = True
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


# Definition of Visualization specific Objects
class VisuObject:
    def __init__(self, position:pygame.Vector2) -> None:
        self.position = position

    def draw(self, viewport) -> None:
        raise NotImplementedError()


class Crosshair(VisuObject):
    height = 10
    width = 10
    color = "red"

    def draw(self, viewport) -> None:
        pygame.draw.line(
            viewport.screen,
            self.color,
            self.position + (self.height,0),
            self.position - (self.height,0))
        pygame.draw.line(
            viewport.screen,
            self.color,
            self.position + (0,self.width),
            self.position - (0,self.width)
        )


class MiniMap(VisuObject):
    def __init__(self, temp_objects, size=None, position=None, scale=None):
        self.name = "MiniMap"
        self.temp_objects = temp_objects
        self.active = True
        self.color = "red"
        if scale is None:
            scale = 0.5
        self.scale = scale
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
        for obj in self.temp_objects:
            if isinstance(obj, type):
                obj.draw_simple(self.minimap, self.offset, self.scale)

    def draw_viewport_outline(self, viewport) -> None:
        view_rect = pygame.Rect(
            self.offset-(viewport.window.size)*self.scale*viewport.view.z/2-viewport.view.offset * self.scale,
            viewport.window.size*self.scale*viewport.view.z,
        )
        pygame.draw.rect(
            self.minimap,
            self.color,
            view_rect,
            width=1,
        )
        pygame.draw.circle(
            self.minimap,
            self.color,
            self.offset-viewport.view.offset*self.scale,
            3,
            width=1,
        )

    def render_minimap(self, viewport) -> pygame.Surface:
        clear(self.minimap)
        self.draw_simple_objects_of_type(VisuConnector)
        self.draw_simple_objects_of_type(VisuStation)
        self.draw_simple_objects_of_type(VisuCarrier)
        self.draw_viewport_outline(viewport)
        return self.minimap

    def draw(self, viewport) -> None:
        if self.active:
            pygame.draw.rect(viewport.surface, self.color, self.Rect)
            viewport.surface.blit(self.render_minimap(viewport), self.position)


class Tooltip(VisuObject):
    def __init__(self, temp_objects):
        self.temp_objects = temp_objects
        self.type = None

    @property
    def mouse_pos(self) -> pygame.Vector2:
        return pygame.Vector2(pygame.mouse.get_pos())

    def render_number(self, surface, number) -> None:
        font = pygame.font.SysFont(None, int(20))
        processing_time_text = font.render(str(number), True, 'black')
        processing_time_rect = processing_time_text.get_rect(
            left=self.mouse_pos.x-30,
            top=self.mouse_pos.y-20,
        )
        background_rect = processing_time_rect.inflate(4, 4)
        pygame.draw.rect(
            surface,
            "white",
            background_rect,
            border_radius = 8,
        )
        pygame.draw.rect(
            surface,
            "black",
            background_rect,
            width = 1,
            border_radius = 8,
            )
        surface.blit(processing_time_text, processing_time_rect)

    def render_processing_graph(self, surface, processing_time) -> None:
        height = max(processing_time)+10
        processing_rect = pygame.Rect(
            self.mouse_pos.x+5,
            self.mouse_pos.y - height,
            100,
            height,
        )
        background_rect = processing_rect.inflate(8, 8)
        pygame.draw.rect(
            surface,
            "white",
            background_rect,
            border_radius = 8,
        )
        pygame.draw.rect(
            surface,
            "black",
            background_rect,
            width = 1,
            border_radius = 8,
            )
        for i, entry in enumerate(processing_time):
            pygame.draw.circle(
                surface,
                "blue",
                self.mouse_pos + (i+5, -entry),
                1
            )

    def draw(self, viewport):
        for obj in self.temp_objects:
            if not obj.hovered:
                pass
            elif isinstance(obj, VisuStation):
                if len(obj.processing_time) > 0:
                    self.render_number(viewport.surface, obj.processing_time[-1])
                    self.render_processing_graph(viewport.surface, obj.processing_time)
            elif isinstance(obj, VisuCarrier):
                self.render_number(viewport.surface, obj.fill)
                
            

#Start of Simulation Equivalent Classes

class VisuEquivalent(VisuObject):
    def __init__(self, obj:ConnectionData):
        self.name = obj.name
        self.position = obj.position
        self.color = "gray"
        self.window_center = pygame.Vector2(0, 0)
        self.view_offset = pygame.Vector2(0, 0)
        self.view_z = 1.0

    def __eq__(self, other:str) -> bool:
        return self.name == other

    @property
    def hovered(self) -> bool:
        return False

    def update(self, obj:ConnectionData) -> None:
        self.position = obj.position

    def update_offset(self, viewport) -> None:
        self.window_center = viewport.window.center
        self.view_offset = viewport.view.offset
        self.view_z = viewport.view.z

    def draw(self, surface) -> None:
        raise NotImplementedError()


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
        self.processing_time = []

    @property
    def station_color(self) -> str:
        station_color = self.color_mapping[self.mode]
        if not self.on:
            station_color = self.color
        return station_color

    @property
    def Rect(self) -> pygame.Rect:
        Rect = pygame.Rect(
            self.window_center.x + (self.view_offset.x + self.position.x - self.width/2)/self.view_z,
            self.window_center.y + (self.view_offset.y + self.position.y - self.height/2)/self.view_z,
            self.width/self.view_z,
            self.height/self.view_z,
        )
        return Rect

    @property
    def hovered(self) -> bool:
        return self.Rect.collidepoint(pygame.mouse.get_pos())

    def update(self, obj:ConnectionData) -> None:
        super().update(obj=obj)
        self.mode = obj.mode
        self.on = obj.on
        self.processing_time.append(round(float(obj.processing_time),1))
        if len(self.processing_time) > 100:
            self.processing_time.pop(0)

    def renderBlock(self, surface) -> None:
        pygame.draw.rect(
            surface,
            self.station_color,
            self.Rect,
            border_radius = int(max(1,self.radius/self.view_z))
        )

    def renderName(self, surface) -> None:
        font = pygame.font.SysFont(None, int(20/self.view_z))
        name_text = font.render(self.name, True, 'black')
        surface.blit(
            name_text,
            name_text.get_rect(
                center=self.window_center + (self.view_offset + self.position + (0, -0.7*self.height))/self.view_z
            )
        )

    def render_outline(self, surface) -> None:
        pygame.draw.rect(
            surface,
            "blue",
            self.Rect,
            width = int(max(1, self.width/10/self.view_z)),
            border_radius = int(max(1, self.radius/self.view_z))
        )

    def draw(self, surface) -> None:
        self.renderBlock(surface)
        self.renderName(surface)
        if self.hovered:
            self.render_outline(surface)

    def draw_simple(self, surface:pygame.Surface, offset:pygame.Vector2, scale:float) -> None:
        pygame.draw.circle(
            surface,
            self.station_color,
            offset + self.position*scale,
            int(self.height/2 * scale)
        )


class VisuSwitch(VisuStation):
    def __init__(self, obj:ConnectionData):
        super().__init__(obj=obj)
        self.pos_in = obj.pos_in_out[0]
        self.pos_out = obj.pos_in_out[1]
        self.connector_color = "gray"

    def update(self, obj:ConnectionData) -> None:
        super().update(obj=obj)
        self.pos_in = obj.pos_in_out[0]
        self.pos_out = obj.pos_in_out[1]

    def render_connections(self, surface) -> None:
        pygame.draw.circle(
            surface,
            self.connector_color,
            self.window_center + (self.view_offset + self.position)/self.view_z,
            self.width/4/self.view_z
        )
        pygame.draw.line(
            surface,
            self.connector_color,
            self.window_center + (self.view_offset + self.pos_in)/self.view_z,
            self.window_center + (self.view_offset + self.position)/self.view_z,
            width=int(10/self.view_z)
        )
        pygame.draw.line(
            surface,
            self.connector_color,
            self.window_center + (self.view_offset + self.position)/self.view_z,
            self.window_center + (self.view_offset + self.pos_out)/self.view_z,
            width=int(10/self.view_z)
        )

    def draw(self, surface) -> None:
        super().draw(surface=surface)
        self.render_connections(surface)


class VisuConnector(VisuEquivalent):
    def __init__(self, obj:ConnectionData) -> None:
        super().__init__(obj=obj)
        self.endpoint = obj.endpoint
        self.width = 10

    def renderLine(self, surface) -> None:
        pygame.draw.line(
            surface,
            self.color,
            self.window_center + (self.view_offset + self.position)/self.view_z,
            self.window_center + (self.view_offset + self.endpoint)/self.view_z,
            width=int(self.width/self.view_z)
        )

    def draw(self, surface) -> None:
        self.renderLine(surface)

    def draw_simple(self, surface:pygame.Surface, offset:pygame.Vector2, scale:float) -> None:
        pygame.draw.line(
            surface,
            self.color,
            offset + self.position*scale,
            offset + self.endpoint*scale,
            width=int(self.width*scale)
        )


class VisuBuffer(VisuConnector):
    def __init__(self, obj:ConnectionData) -> None:
        super().__init__(obj=obj)
        self.capacity = obj.capacity

    def renderSlots(self, surface) -> None:
        length = self.endpoint-self.position
        snippet = length/(self.capacity+1)
        for n in range(self.capacity):
            pygame.draw.circle(
                surface,
                self.color,
                self.window_center + (self.view_offset + self.position + snippet*(n+1))/self.view_z,
                int(self.width/self.view_z)
            )

    def draw(self, surface) -> None:
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
            self.window_center.x + (self.view_offset.x + self.position.x - self.width/2)/self.view_z,
            self.window_center.y + (self.view_offset.y + self.position.y - self.height/2)/self.view_z,
            self.width/self.view_z,
            self.height/self.view_z,
        )
        return Rect

    @property
    def hovered(self) -> bool:
        return self.Rect.collidepoint(pygame.mouse.get_pos())

    @property
    def Items(self) -> pygame.Rect:
        Items = self.Rect.inflate(-4/self.view_z, -4/self.view_z)
        Items.inflate_ip(-(self.width-4/self.view_z)*(1-self.fill)/self.view_z, 0)
        Items.move_ip(-(self.width-4/self.view_z)*(1-self.fill)/2/self.view_z, 0)
        return Items

    def renderBlock(self, surface) -> None:
        pygame.draw.rect(
            surface,
            self.color,
            self.Rect,
        )

    def renderItems(self, surface) -> None:
        pygame.draw.rect(
            surface,
            self.item_color,
            self.Items
        )

    def draw(self, surface) -> None:
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



def find_line_bounds(temp_visu_objects) -> pygame.Vector2:
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

def find_line_size(temp_visu_objects, line_bounds=None) -> pygame.Vector2:
    if line_bounds is None:
        line_bounds = find_line_bounds(temp_visu_objects)
    line_width = line_bounds['lower_right'].x - line_bounds['upper_left'].x
    line_height = line_bounds['lower_right'].y - line_bounds['upper_left'].y
    line_center = line_bounds['upper_left'] + (line_width/2,line_height/2)
    return (line_width, line_height, line_center)

def clear(surface:pygame.Surface) -> None:
    surface.fill("white")

def check_user_input(dt, viewport, minimap, connection) -> bool:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            connection.halt_event.set()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_m:
                minimap.toggle()
        elif event.type == pygame.MOUSEWHEEL:
            viewport.view.z += 5 * event.y * viewport.view.z * dt
    
    _mouse = pygame.mouse.get_pressed(num_buttons=3)
    mouse_rel = pygame.mouse.get_rel()
    if _mouse[0]:
        viewport.view.x += mouse_rel[0] * viewport.view.z
        viewport.view.y += mouse_rel[1] * viewport.view.z
    keys = pygame.key.get_pressed()
    if keys[pygame.K_q]:
        viewport.view.z -= 3*viewport.view.z*dt
    if keys[pygame.K_e]:
        viewport.view.z += 3*viewport.view.z*dt
    if keys[pygame.K_w] or keys[pygame.K_UP]:
        viewport.view.y += 300*viewport.view.z*dt
    if keys[pygame.K_s] or keys[pygame.K_DOWN]:
        viewport.view.y -= 300*viewport.view.z*dt
    if keys[pygame.K_a] or keys[pygame.K_LEFT]:
        viewport.view.x += 300*viewport.view.z*dt
    if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
        viewport.view.x -= 300*viewport.view.z*dt
    if keys[pygame.K_h] and keys[pygame.K_LSHIFT]:
        connection.halt_event.set()
    viewport.view.z = max(0.5,min(10,viewport.view.z))
    return True

def draw_objects_of_type(type, viewport, manager) -> None:
    for obj in manager.temp_visu_objects:
        if isinstance(obj, type):
            obj.draw(viewport.surface)
    for obj in manager.perm_visu_objects:
        if isinstance(obj, type):
            obj.draw(viewport)


class Viewport:
    def __init__(self, screen):
        self.window = Window()
        self.view = None
        self.screen = screen

    @property
    def surface(self):
        return self.screen

    def set_initial_view(self, line_size=None):
        if line_size is None:
            line_width, line_height, line_center = find_line_size()
        else:
            line_width, line_height, line_center = line_size
        x = -line_center.x
        y = -line_center.y
        x_scalar = line_width / (self.window.size.x-100)
        y_scalar = line_height / (self.window.size.y-100)
        scalar = max(x_scalar,y_scalar)
        if scalar < 1:
            z = 1
        else:
            z = round(scalar,1)
        self.view = View(x,y,z)

    @property
    def is_initialized(self):
        return self.view is not None


def draw_scene(viewport: Viewport, manager) -> None:
    clear(viewport.screen)

    for cls in [VisuConnector, VisuStation, VisuCarrier, Crosshair, MiniMap, Tooltip]:
        draw_objects_of_type(cls, viewport, manager)


class VisuManager:
    object_mapping = {
        "station": VisuStation,
        "process": VisuStation,
        "source": VisuStation,
        "sink": VisuStation,
        "switch": VisuSwitch,
        "buffer": VisuBuffer,
        "carrier": VisuCarrier
    }
    temp_objects = (VisuStation, VisuSwitch, VisuBuffer, VisuCarrier)
    def __init__(self, connection):
        self.perm_visu_objects = []
        self.temp_visu_objects = []
        self.connection = connection

    def receive_data(self):
        self.connection.recieve_all()

    def add(self, obj) -> None:
        self.perm_visu_objects.append(obj)

    def create(self, obj_spec) -> None:

        obj = self.object_mapping[obj_spec.type](obj_spec)

        if isinstance(obj, self.temp_objects):
            self.temp_visu_objects.append(obj)
        else:
            self.perm_visu_objects.append(obj)
    
    def remove(self, obj):
        self.temp_visu_objects.remove(obj)

    @property
    def data(self):
        return self.connection.data

    def heartbeat(self) -> None:
        if self.connection.new_data:
            remove_from_visu = []
            for visu_obj in self.temp_visu_objects:
                if visu_obj not in self.data:
                    remove_from_visu.append(visu_obj)
                else:
                    i = self.data.index(visu_obj.name)
                    visu_obj.update(self.data[i])
            for visu_obj in remove_from_visu:
                self.remove(visu_obj)
            remove_from_visu = []
            for sim_obj in self.data:
                if sim_obj not in self.temp_visu_objects:
                    self.create(sim_obj)
            self.connection.new_data = False

    def update_offsets(self, viewport) -> None:
        for visu_obj in self.temp_visu_objects:
            visu_obj.update_offset(viewport)
    

def run_visualization(connection: Communication) -> None:
    pygame.init()
    screen = pygame.display.set_mode(Window.size)
    clock = pygame.time.Clock()
    dt = 0
    initialized = False
    running = True

    viewport = Viewport(screen)

    manager = VisuManager(connection)
    try:
        while running:
            if viewport.is_initialized:
                check_user_input(dt, viewport, manager.perm_visu_objects[1], connection)
            if connection.stop_event.is_set():
                running = False
                break

            manager.receive_data()
            manager.heartbeat()
    
            if not viewport.is_initialized and connection.data is not None:
                manager.add(Tooltip(manager.temp_visu_objects))
                manager.add(Crosshair(viewport.window.center))
                manager.add(MiniMap(manager.temp_visu_objects, find_line_size(manager.temp_visu_objects), scale=0.2))
                viewport.set_initial_view(line_size=find_line_size(manager.temp_visu_objects))
            if viewport.is_initialized:
                manager.update_offsets(viewport)
                draw_scene(viewport, manager)
            if connection.halt_event.is_set():
                clear(screen)
    
            pygame.display.flip()
            dt = clock.tick(60)/1000
    finally:
        pygame.quit()
        connection.stop_event.set()