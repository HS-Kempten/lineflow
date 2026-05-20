import pygame
import logging
from queue import Empty
from multiprocessing import Queue, Event


logger = logging.getLogger(__name__)

class ConnectionData:
    """Object for transfering data to Visualization"""

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
            self.data = None

    def recieve_all(self):
        while True:
            try:
                self.data = self.queue_in.get_nowait()
            except Empty:
                break

    def send(self, data):
        self.queue_out.put(data)

    def clear_data(self):
        self.data = None


class UserInput:
    def __init__(self, visualization, connection):
        self.visu = visualization
        self.connection = connection
        self.mouse_pos = pygame.Vector2(0, 0)
        self.mouse_rel = pygame.Vector2(0, 0)

        self.modify_obj = None
        self.leftclick_pos = pygame.Vector2(0, 0)
        self.dropdown = False

    @property
    def rightclick(self):
        return pygame.mouse.get_pressed(num_buttons=3)[0]
    
    @property
    def leftclick(self):
        return pygame.mouse.get_pressed(num_buttons=3)[2]

    def check(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_m:
                    self.visu.show_minimap = not self.visu.show_minimap
            elif event.type == pygame.MOUSEWHEEL:
                self.visu.viewpoint.z += 5 * event.y * self.visu.viewpoint.z * self.visu.dt
    
        self.mouse_rel = pygame.Vector2(pygame.mouse.get_rel())
        self.mouse_pos = pygame.Vector2(pygame.mouse.get_pos())

        if self.rightclick and self.dropdown is False:
            self.visu.viewpoint.x += self.mouse_rel.x * self.visu.viewpoint.z
            self.visu.viewpoint.y += self.mouse_rel.y * self.visu.viewpoint.z

        keys = pygame.key.get_pressed()
        if keys[pygame.K_q]:
            self.visu.viewpoint.z -= 3*self.visu.viewpoint.z*self.visu.dt
        if keys[pygame.K_e]:
            self.visu.viewpoint.z += 3*self.visu.viewpoint.z*self.visu.dt
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            self.visu.viewpoint.y += 300*self.visu.viewpoint.z*self.visu.dt
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            self.visu.viewpoint.y -= 300*self.visu.viewpoint.z*self.visu.dt
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            self.visu.viewpoint.x += 300*self.visu.viewpoint.z*self.visu.dt
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            self.visu.viewpoint.x -= 300*self.visu.viewpoint.z*self.visu.dt
        if keys[pygame.K_h] and keys[pygame.K_LSHIFT]:
            self.visu.connection.halt_event.set()
        self.visu.viewpoint.z = max(0.5,min(10,self.visu.viewpoint.z))
        self.visu.view = pygame.Vector2(self.visu.viewpoint.x, self.visu.viewpoint.y)
        return True

    def hover_over(self, obj):
        obj_pos = self.visu.center + (self.visu.view + obj.position)/self.visu.viewpoint.z
        diff_x = abs(obj_pos.x - self.mouse_pos.x)
        diff_y = abs(obj_pos.y - self.mouse_pos.y)
        max_diff = obj.size/2/self.visu.viewpoint.z
        if diff_x < max_diff and diff_y < max_diff:
            if self.leftclick and self.dropdown is False:
                self.dropdown = True
                self.modify_obj = obj
                self.leftclick_pos = self.mouse_pos
            return True
        else:
            return False

    def dropdown_menu(self):
        if self.modify_obj.on:
            dropdown_input = f"Turn Off"
            state = 0
        elif not self.modify_obj.on:
            dropdown_input = f"Turn On"
            state =  1

        self.draw_dropdown_menu(dropdown_input)

        dropdown_vector = self.mouse_pos - self.leftclick_pos
        if dropdown_vector.x > 100 or dropdown_vector.x < -5 or dropdown_vector.y < -5 or dropdown_vector.y > 30:
            self.dropdown = False
        elif self.rightclick:
            self.connection.send({self.modify_obj.name:{'on': state}})
            self.dropdown = False
        else:
            pass

    def draw_dropdown_menu(self, dropdown_input):
        dropdown_window = pygame.Rect(self.leftclick_pos,(100, 30))
        pygame.draw.rect(
            self.visu.screen,
            'white',
            dropdown_window
        )
        pygame.draw.rect(
            self.visu.screen,
            'black',
            dropdown_window,
            width = 2
        )
        font = pygame.font.SysFont(None, 20)
        dropdown_text = font.render(dropdown_input,True,'black')
        self.visu.screen.blit(dropdown_text, self.leftclick_pos + (5, 8))


class Visualization:
    
    def __init__(
        self,
        size=None,
        viewpoint=None,
        connection=None,
    ):

        if size is None:
            size = (1280, 720)
        self.size = pygame.Vector2(size)

        if viewpoint is not None:
            viewpoint = pygame.Vector3(viewpoint)
            self.view = pygame.Vector2(viewpoint.x, viewpoint.y)
        self.viewpoint = viewpoint
        
        self.connection = connection

        self.center = pygame.Vector2(self.size.x/2, self.size.y/2)

        self.initial_view_data = False

        self.line_bounds = None
        self.show_minimap = True

        self.user_input = UserInput(self, self.connection)

    @property
    def viewpoint_is_set(self):
        return self.viewpoint is not None

    def find_line_bounds(self):
        x_positions = []
        y_positions = []
        for item in self.connection.data:
            if 'position' in item:
                x_positions.append(item.position.x)
                y_positions.append(item.position.y)
        self.line_bounds = dict(
            upper_left=pygame.Vector2(min(x_positions), min(y_positions)),
            lower_right=pygame.Vector2(max(x_positions), max(y_positions))
        )

    def find_line_size(self):
        if self.line_bounds is None:
            self.find_line_bounds()
        line_width = self.line_bounds['lower_right'].x - self.line_bounds['upper_left'].x
        line_height = self.line_bounds['lower_right'].y - self.line_bounds['upper_left'].y
        line_center = self.line_bounds['upper_left'] + (line_width/2,line_height/2)
        return line_width, line_height, line_center

    def set_initial_viewpoint(self):
        line_width, line_height, line_center = self.find_line_size()
        x = -line_center.x
        y = -line_center.y
        x_scalar = line_width / (self.size.x-100)
        y_scalar = line_height / (self.size.y-100)
        scalar = max(x_scalar,y_scalar)
        if scalar < 1:
            z = 1
        else:
            z = round(scalar,1)
        self.viewpoint = pygame.Vector3(x, y, z)
        self.view = pygame.Vector2(x, y)

    def clear(self):
        self.screen.fill('white')

    def check_connection(self):
        self.connection.recieve_all()
        if self.connection.data is not None:
            self.initial_view_data = True
            self.connection.data.sort()
            
    def draw(self):
        self.tooltip = None
        draw_mapping = dict(
            carrier=self.draw_carrier,
            connector=self.draw_connector,
            station=self.draw_station,
            info=self.draw_info,
            actions=self.draw_actions
        )
        for item in self.connection.data:
            try:
                draw_mapping[item.type](item)
            except KeyError:
                logger.warning(
                    f"Unknown item type: {item.type} will not be visualized."
                )

    def draw_connector(self, connector):
        color = 'gray'
        pygame.draw.line(
            self.screen,
            color,
            self.center + (self.view + connector.start)/self.viewpoint.z,
            self.center + (self.view + connector.end)/self.viewpoint.z,
            width=int(10/self.viewpoint.z)
        )
        length = connector.end/self.viewpoint.z-connector.start/self.viewpoint.z
        snippet = length/(connector.n_slots+1)
        for n in range(connector.n_slots):
            pygame.draw.circle(
                self.screen,
                color,
                self.view/self.viewpoint.z + self.center + connector.start/self.viewpoint.z + snippet*(n+1),
                int(10/self.viewpoint.z)
            )
    
    def get_station_color(self, station):
        color_mapping = {
            'working': 'green',
            'waiting': 'yellow',
            'failing': 'red'
        }
        color = color_mapping[station.mode]
        if not station.on:
            color = 'gray'
        return color

    def draw_station(self, station):
        width = 30
        height = 30
        font = pygame.font.SysFont(None,int(20/self.viewpoint.z))
        color = self.get_station_color(station)
        pygame.draw.rect(
            self.screen,
            color,
            pygame.Rect(
                self.center.x + (self.viewpoint.x + station.position.x-width/2)/self.viewpoint.z,
                self.center.y + (self.viewpoint.y + station.position.y-height/2)/self.viewpoint.z,
                width/self.viewpoint.z,
                height/self.viewpoint.z
            ),
            border_radius=int(max(1,8/self.viewpoint.z))
        )
        name_text = font.render(station.name,True,'black')
        self.screen.blit(
            name_text,
            name_text.get_rect(
                center=self.center + (self.view + station.position+(0,-0.7*height))/self.viewpoint.z
            )
        )
        if 'worker_skill' in station or 'magazine' in station:
            font = pygame.font.SysFont(None,int(14/self.viewpoint.z))
            if 'worker_skill' in station:
                info_text = font.render('W=' + str(station.worker_skill),False,'black')
            else:
                info_text = font.render('C=' + str(station.magazine),False,'black')
            self.screen.blit(
                info_text,
                info_text.get_rect(
                    center=self.center + (self.view + station.position)/self.viewpoint.z
                )
            )
        if 'pos_in_out' in station:
            switch_color = 'gray'
            if not station.on:
                switch_color = pygame.Color(100,100,100)
            pygame.draw.circle(
                self.screen,
                switch_color,
                self.center + (self.view + station.position)/self.viewpoint.z,
                6/self.viewpoint.z
            )
            for pos in station.pos_in_out:
                pygame.draw.line(
                    self.screen,
                    switch_color,
                    self.center + (self.view + station.position)/self.viewpoint.z,
                    self.center + (self.view + pos)/self.viewpoint.z,
                    width=int(5/self.viewpoint.z)
                )
        station.size = 30
        if self.user_input.hover_over(station):
            try:
                p_time = round(float(station.processing_time), 2)
            except AttributeError:
                p_time = "NAN"
            self.tooltip = f"P_time: {p_time}"

    def draw_tooltip(self):
        tooltip_window = pygame.Rect(self.user_input.mouse_pos + (10, 0),(100, 30))
        pygame.draw.rect(
            self.screen,
            'white',
            tooltip_window,
            border_radius = 10
        )
        pygame.draw.rect(
            self.screen,
            'black',
            tooltip_window,
            width = 2,
            border_radius = 10
        )
        font = pygame.font.SysFont(None, 20)
        tooltip_text = font.render(self.tooltip,True,'black')
        self.screen.blit(tooltip_text, self.user_input.mouse_pos + (15, 8))

    def draw_timeline(self):
        

    def draw_carrier(self, carrier):
        height = 10
        width = 30
        pygame.draw.rect(
            self.screen,
            'black',
            pygame.Rect(
                self.center.x + (self.viewpoint.x + carrier.position.x-width/2)/self.viewpoint.z,
                self.center.y + (self.viewpoint.y + carrier.position.y-height/2)/self.viewpoint.z,
                width/self.viewpoint.z,
                height/self.viewpoint.z
            )
        )
        pygame.draw.rect(
            self.screen,
            'orange',
            pygame.Rect(
                self.center.x + (self.viewpoint.x + carrier.position.x-width*0.8/2)/self.viewpoint.z,
                self.center.y + (self.viewpoint.y + carrier.position.y-height*0.8/2)/self.viewpoint.z,
                width*0.8*carrier.fill/self.viewpoint.z,
                height*0.8/self.viewpoint.z
            )
        )
        if 'name' in carrier:
            font = pygame.font.SysFont(None, int(12/self.viewpoint.z))
            text = font.render(carrier.name,False,'blue')
            self.screen.blit(
                text,
                text.get_rect(
                    center=self.center + (self.view + carrier.position)/self.viewpoint.z + (0,-1.3*height/self.viewpoint.z)
                )
            )

    def draw_info(self, info):
        font = pygame.font.SysFont(None, 20)
        time = font.render( 'T={:.2f}'.format(info.time), True, 'black', 'white')
        n_parts = font.render( f"#Parts={info.n_parts}", True, 'black', 'white')
        self.screen.blit(time, time.get_rect(center=(30, 30)))
        self.screen.blit(n_parts, n_parts.get_rect(center=(30, 50)))

    def draw_actions(self, actions):
        font = pygame.font.SysFont(None, 20)
        for n, actor_actions in enumerate(actions.actions.items()):
            actor = actor_actions[0]
            if len(actor_actions[1]) == 1:
                actions = "".join(f"{action[0]}={action[1]}" for action in actor_actions[1].items())
            else:
                actions = "".join(f"{action[0]}={action[1]}, " for action in actor_actions[1].items())
            text = font.render( f'{actor}: {actions}', True, 'black', 'white')
            self.screen.blit(text, text.get_rect(center=(self.center.x, 30+n*22)))

    def draw_user_input(self):
        font = pygame.font.SysFont(None, 24)
        text = font.render(
            "W: up, S: down, A: left, D: right, Q: zoom in, E: zoom out, Shift+H: Exit, M: toggle minimap",
            True,
            'black',
            'white'
        )
        self.screen.blit(text, text.get_rect(left=50,top=self.size.y-40))

    def draw_loading(self):
        font = pygame.font.SysFont(None, 48)
        text = font.render("Loading Scene...", True, 'black')
        self.screen.blit(text, text.get_rect(center=self.center))

    def draw_shutdown(self):
        font = pygame.font.SysFont(None, 48)
        text = font.render("Shutting down...", True, 'black')
        self.screen.blit(text, text.get_rect(center=self.center))

    def draw_crosshair(self):
        pygame.draw.line( self.screen, 'red', self.center + (10,0), self.center - (10,0))
        pygame.draw.line( self.screen, 'red', self.center + (0,10), self.center - (0,10))

    def draw_minimap(self):
        if self.line_bounds is None:
            self.find_line_bounds()

        #setup minimap
        downscale = 5
        buffer = pygame.Vector2(20, 20)
        line_diagonal = self.line_bounds['lower_right'] - self.line_bounds['upper_left']
        minimap_size = pygame.Vector2(line_diagonal / downscale + buffer)
        minimap = pygame.Surface(minimap_size)
        minimap.fill('white')
        minimap_pos = pygame.Vector2(self.size.x - minimap_size.x, 0)
        draw_position = - self.line_bounds['upper_left'] / downscale + buffer /2
        pygame.draw.rect(minimap, 'black', pygame.Rect((0,0), minimap_size), width=2)

        #draw on minimap
        for item in self.connection.data:
            if item.type == 'connector':
                pygame.draw.line(
                    minimap,
                    'gray',
                    draw_position + item.start / downscale,
                    draw_position + item.end / downscale,
                )
            if item.type == 'station':
                color = self.get_station_color(item)
                pygame.draw.circle(
                    minimap,
                    color,
                    draw_position + item.position / downscale,
                    5
                )
            if item.type == 'carrier':
                pygame.draw.circle(
                    minimap,
                    'orange',
                    draw_position + item.position / downscale,
                    3
                )

        #draw outline of current view and crosshair
        view_outline = pygame.Rect(
            draw_position - self.view / downscale - self.size / downscale * self.viewpoint.z / 2,
            self.size / downscale * self.viewpoint.z
        )
        pygame.draw.line(
            minimap,
            'red',
            draw_position - self.view / downscale + (3,0),
            draw_position - self.view / downscale - (3,0)
        )
        pygame.draw.line(
            minimap,
            'red',
            draw_position - self.view / downscale + (0,3),
            draw_position - self.view / downscale - (0,3)
        )
        pygame.draw.rect(minimap, 'red', view_outline, width=1)
        
        #blit minimap onto screen
        self.screen.blit(minimap,minimap_pos)
        
    def run(self):

        pygame.init()
        self.screen = pygame.display.set_mode(self.size)
        self.clock = pygame.time.Clock()

        try:
            while True:
                if self.connection.stop_event.is_set():
                    break

                if self.viewpoint_is_set and not self.user_input.check():
                    break

                self.check_connection()

                if not self.viewpoint_is_set and self.initial_view_data:
                    self.set_initial_viewpoint()

                self.clear()
                
                if not self.viewpoint_is_set:
                    self.draw_loading()
                else:
                    self.draw()
                    self.draw_user_input()
                    self.draw_crosshair()

                if self.tooltip is not None and self.user_input.dropdown is False:
                    self.draw_tooltip()
                elif self.user_input.dropdown:
                    self.user_input.dropdown_menu()

                if self.viewpoint_is_set and self.show_minimap:
                    self.draw_minimap()

                if self.connection.halt_event.is_set():
                    self.clear()
                    self.draw_shutdown()

                pygame.display.flip()
                
                self.dt = self.clock.tick(60)/1000
        finally:
            pygame.quit()
            self.connection.stop_event.set()


def start_visualization(connection, size=None, viewpoint=None):
    visualization = Visualization(connection=connection, size=size, viewpoint=viewpoint)
    visualization.run()
