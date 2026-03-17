import pygame
from queue import Empty

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

class Visualization:
    
    def __init__(
        self,
        size=None,
        viewpoint=None,
        points=None,
        connection=None,
        stop_event=None,
        ):

        if size is None:
            size = (1280,720)
        self.size = size
        if viewpoint is None:
            viewpoint = (0,0,1)
        self.viewpoint = pygame.Vector3(viewpoint)

        self.connection = connection
        self.stop_event = stop_event

        self.center = pygame.Vector2(self.size[0]/2, self.size[1]/2)

        self.connection_data = []
        self.stations = []
        self.connectors = []
        self.carriers = []

    def teardown(self):
        self.running = False

    def clear(self):
        self.screen.fill('white')

    def get_from_connection(self):
        #if not self.connection.empty():
        #    self.connection_data = self.connection.get()
        while True:
            try:
                self.connection_data = self.connection.get_nowait()
            except Empty:
                break

    def sort_connection_data(self):
        self.carriers = []
        self.connectors = []
        self.stations = []
        for item in self.connection_data:
            if item['type'] == 'carrier':
                self.carriers.append(item)
            elif item['type'] == 'connector':
                self.connectors.append(item)
            elif item['type'] == 'station':
                self.stations.append(item)

    def check_connection(self):
        self.get_from_connection()
        self.sort_connection_data()
            
    def draw_connectors(self):
        for connector in self.connectors:
            pygame.draw.line(
                self.screen,
                'gray',
                (self.viewpoint.x,self.viewpoint.y) + self.center + connector['start']/self.viewpoint.z,
                (self.viewpoint.x,self.viewpoint.y) + self.center + connector['end']/self.viewpoint.z,
                width=int(10/self.viewpoint.z)
            )
            length = connector['end']/self.viewpoint.z-connector['start']/self.viewpoint.z
            snippet = length/(connector['n_slots']+1)
            for n in range(connector['n_slots']):
                pygame.draw.circle(
                    self.screen,
                    'gray',
                    (self.viewpoint.x,self.viewpoint.y) + self.center + connector['start']/self.viewpoint.z + snippet*(n+1),
                    int(10/self.viewpoint.z)
                )

    def draw_stations(self):
        width = 30
        height = 30
        font = pygame.font.SysFont(None,int(20/self.viewpoint.z))
        for station in self.stations:
            color = 'black'
            if not 'mode' in station:
                pass
            elif station['mode'] == 'working':
                color = 'green'
            elif station['mode'] == 'waiting':
                color = 'yellow'
            elif station['mode'] == 'failing':
                color = 'red'
            elif station['mode'] == 'off':
                color = 'gray'

            pygame.draw.rect(
                self.screen,
                color,
                pygame.Rect(
                    self.viewpoint.x + self.center.x + (station['position'].x-width/2)/self.viewpoint.z,
                    self.viewpoint.y + self.center.y + (station['position'].y-height/2)/self.viewpoint.z,
                    width/self.viewpoint.z,
                    height/self.viewpoint.z
                ),
                border_radius=int(max(1,8/self.viewpoint.z))
            )
            name_text = font.render(station['name'],True,'black')
            self.screen.blit(
                name_text,
                name_text.get_rect(
                    center=(self.viewpoint.x,self.viewpoint.y) + self.center + (station['position']+(0,-0.7*height))/self.viewpoint.z
                )
            )
            if 'worker_skill' in station or 'magazine' in station:
                font = pygame.font.SysFont(None,int(14/self.viewpoint.z))
                if 'worker_skill' in station:
                    info_text = font.render('W=' + str(station['worker_skill']),False,'black')
                else:
                    info_text = font.render('C=' + str(station['magazine']),False,'black')
                self.screen.blit(
                    info_text,
                    info_text.get_rect(
                        center=(self.viewpoint.x,self.viewpoint.y) + self.center + station['position']/self.viewpoint.z
                    )
                )
            if 'pos_in_out' in station:
                pygame.draw.circle(
                    self.screen,
                    'gray',
                    (self.viewpoint.x,self.viewpoint.y) + self.center + station['position']/self.viewpoint.z,
                    6/self.viewpoint.z
                )
                for pos in station['pos_in_out']:
                    pygame.draw.line(
                        self.screen,
                        'gray',
                        (self.viewpoint.x,self.viewpoint.y) + self.center + station['position']/self.viewpoint.z,
                        (self.viewpoint.x,self.viewpoint.y) + self.center + pos/self.viewpoint.z,
                        width=int(5/self.viewpoint.z)
                    )

    def draw_carriers(self):
        height = 10
        width = 30
        for carrier in self.carriers:
            pygame.draw.rect(
                self.screen,
                'black',
                pygame.Rect(
                    self.viewpoint.x + self.center.x + (carrier['position'].x-width/2)/self.viewpoint.z,
                    self.viewpoint.y + self.center.y + (carrier['position'].y-height/2)/self.viewpoint.z,
                    width/self.viewpoint.z,
                    height/self.viewpoint.z
                )
            )
            pygame.draw.rect(
                self.screen,
                'orange',
                pygame.Rect(
                    self.viewpoint.x + self.center.x + (carrier['position'].x-width*0.8/2)/self.viewpoint.z,
                    self.viewpoint.y + self.center.y + (carrier['position'].y-height*0.8/2)/self.viewpoint.z,
                    width*0.8*carrier['fill']/self.viewpoint.z,
                    height*0.8/self.viewpoint.z
                )
            )
            if 'name' in carrier:
                font = pygame.font.SysFont(None, int(12/self.viewpoint.z))
                text = font.render(carrier['name'],False,'blue')
                self.screen.blit(
                    text,
                    text.get_rect(
                        center=(self.viewpoint.x,self.viewpoint.y) + self.center + carrier['position']/self.viewpoint.z + (0,-1.3*height/self.viewpoint.z)
                    )
                )

    def draw_user_input(self):
        font = pygame.font.SysFont(None,24)
        text = font.render("W: up, S: down, A: left, D: right, Q: zoom in, E: zoom out",True,'black')
        self.screen.blit(text,text.get_rect(left=200,top=50))

    def check_user_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.teardown()
        keys = pygame.key.get_pressed()
        if keys[pygame.K_q]:
            self.viewpoint.z -= 3*self.dt
        if keys[pygame.K_e]:
            self.viewpoint.z += 3*self.dt
        if keys[pygame.K_w]:
            self.viewpoint.y -= 300*self.dt
        if keys[pygame.K_s]:
            self.viewpoint.y += 300*self.dt
        if keys[pygame.K_a]:
            self.viewpoint.x -= 300*self.dt
        if keys[pygame.K_d]:
            self.viewpoint.x += 300*self.dt
        self.viewpoint.z = max(0.5,min(10,self.viewpoint.z))

    def run(self):

        pygame.init()
        self.screen = pygame.display.set_mode(self.size)
        self.clock = pygame.time.Clock()
        self.running = True
        while self.running:
            if self.stop_event.is_set():
                self.teardown()
                
            self.check_user_input()
            self.check_connection()
            self.clear()
            self.draw_connectors()
            self.draw_stations()
            self.draw_carriers()
            self.draw_user_input()


            pygame.display.flip()
        
            self.dt = self.clock.tick(60)/1000
        
        pygame.quit()
        self.stop_event.set()

def start_visualization(connection, stop_event):
    visualization = Visualization(connection=connection, stop_event=stop_event)
    visualization.run()
