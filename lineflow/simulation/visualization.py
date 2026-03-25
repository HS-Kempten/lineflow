import pygame
import logging
from queue import Empty


logger = logging.getLogger(__name__)


class Visualization:
    
    def __init__(
        self,
        size=None,
        viewpoint=None,
        connection=None,
        stop_event=None,
        halt_event=None,
    ):

        if size is None:
            size = (1280, 720)
        self.size = size
        if viewpoint is None:
            viewpoint = (0, 0, 1)
        self.viewpoint = pygame.Vector3(viewpoint)
        self.view = pygame.Vector2(self.viewpoint.x, self.viewpoint.y)

        self.connection = connection
        self.stop_event = stop_event
        self.halt_event = halt_event

        self.center = pygame.Vector2(self.size[0]/2, self.size[1]/2)

        self.stations = []
        self.connectors = []
        self.carriers = []
        self.info = None
        self.actions = None
        self.connection_data = []

    def clear(self):
        self.screen.fill('white')

    def get_from_connection(self):
        while True:
            try:
                self.connection_data = self.connection.get_nowait()
            except Empty:
                break

    def sort_connection_data(self):
        self.carriers = []
        self.connectors = []
        self.stations = []
        self.info = None
        self.actions = None
        for item in self.connection_data:
            if item['type'] == 'carrier':
                self.carriers.append(item)
            elif item['type'] == 'connector':
                self.connectors.append(item)
            elif item['type'] == 'station':
                self.stations.append(item)
            elif item['type'] == 'info':
                self.info = item
            elif item['type'] == 'actions':
                self.actions = item
            else:
                logger.warning(
                    f"Unknown item type: {item['type']}"
                    "Will not be visualized."
                )


    def check_connection(self):
        self.get_from_connection()
        self.sort_connection_data()
            
    def draw_connectors(self):
        for connector in self.connectors:
            pygame.draw.line(
                self.screen,
                'gray',
                self.center + (self.view + connector['start'])/self.viewpoint.z,
                self.center + (self.view + connector['end'])/self.viewpoint.z,
                width=int(10/self.viewpoint.z)
            )
            length = connector['end']/self.viewpoint.z-connector['start']/self.viewpoint.z
            snippet = length/(connector['n_slots']+1)
            for n in range(connector['n_slots']):
                pygame.draw.circle(
                    self.screen,
                    'gray',
                    self.view/self.viewpoint.z + self.center + connector['start']/self.viewpoint.z + snippet*(n+1),
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
                    self.center.x + (self.viewpoint.x + station['position'].x-width/2)/self.viewpoint.z,
                    self.center.y + (self.viewpoint.y + station['position'].y-height/2)/self.viewpoint.z,
                    width/self.viewpoint.z,
                    height/self.viewpoint.z
                ),
                border_radius=int(max(1,8/self.viewpoint.z))
            )
            name_text = font.render(station['name'],True,'black')
            self.screen.blit(
                name_text,
                name_text.get_rect(
                    center=self.center + (self.view + station['position']+(0,-0.7*height))/self.viewpoint.z
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
                        center=self.center + (self.view + station['position'])/self.viewpoint.z
                    )
                )
            if 'pos_in_out' in station:
                pygame.draw.circle(
                    self.screen,
                    'gray',
                    self.center + (self.view + station['position'])/self.viewpoint.z,
                    6/self.viewpoint.z
                )
                for pos in station['pos_in_out']:
                    pygame.draw.line(
                        self.screen,
                        'gray',
                        self.center + (self.view + station['position'])/self.viewpoint.z,
                        self.center + (self.view + pos)/self.viewpoint.z,
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
                    self.center.x + (self.viewpoint.x + carrier['position'].x-width/2)/self.viewpoint.z,
                    self.center.y + (self.viewpoint.y + carrier['position'].y-height/2)/self.viewpoint.z,
                    width/self.viewpoint.z,
                    height/self.viewpoint.z
                )
            )
            pygame.draw.rect(
                self.screen,
                'orange',
                pygame.Rect(
                    self.center.x + (self.viewpoint.x + carrier['position'].x-width*0.8/2)/self.viewpoint.z,
                    self.center.y + (self.viewpoint.y + carrier['position'].y-height*0.8/2)/self.viewpoint.z,
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
                        center=self.center + (self.view + carrier['position'])/self.viewpoint.z + (0,-1.3*height/self.viewpoint.z)
                    )
                )

    def draw_info(self):
        if self.info is not None:
            font = pygame.font.SysFont(None, 20)
            time = font.render(
                'T={:.2f}'.format(self.info['time']),
                True,
                'black',
                'white'
            )
            n_parts = font.render(
                f"#Parts={self.info['n_parts']}",
                True,
                'black',
                'white'
            )
            self.screen.blit(time, time.get_rect(center=(30, 30)))
            self.screen.blit(n_parts, n_parts.get_rect(center=(30, 50)))

    def draw_actions(self):
        if self.actions is not None:
            font = pygame.font.SysFont(None, 20)
            for n, actor_actions in enumerate(self.actions['actions'].items()):
                actor = actor_actions[0]
                if len(actor_actions[1]) == 1:
                    actions = "".join(f"{action[0]}={action[1]}" for action in actor_actions[1].items())
                else:
                    actions = "".join(f"{action[0]}={action[1]}, " for action in actor_actions[1].items())
                text = font.render(
                    f'{actor}: {actions}',
                    True,
                    'black',
                    'white'
                )
                self.screen.blit(text, text.get_rect(center=(self.center.x, 30+n*22)))

    def draw_user_input(self):
        font = pygame.font.SysFont(None, 24)
        text = font.render(
            "W: up, S: down, A: left, D: right, Q: zoom in, E: zoom out, Shift+H: Exit",
            True,
            'black',
            'white'
        )
        self.screen.blit(text,text.get_rect(left=50,top=self.size[1]-40))

    def draw_cursor(self):
        pygame.draw.circle(self.screen, 'blue', self.center, 10, 1)
        
    def check_user_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
    
        keys = pygame.key.get_pressed()
        if keys[pygame.K_q]:
            self.viewpoint.z -= 3*self.dt
        if keys[pygame.K_e]:
            self.viewpoint.z += 3*self.dt
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            self.viewpoint.y += 300*self.dt
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            self.viewpoint.y -= 300*self.dt
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            self.viewpoint.x += 300*self.dt
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            self.viewpoint.x -= 300*self.dt
        if keys[pygame.K_h] and keys[pygame.K_LSHIFT]:
            self.halt_event.set()
        self.viewpoint.z = max(0.5,min(10,self.viewpoint.z))
        self.view = pygame.Vector2(self.viewpoint.x, self.viewpoint.y)
        return True

    def run(self):

        pygame.init()
        self.screen = pygame.display.set_mode(self.size)
        self.clock = pygame.time.Clock()

        try:
            while True:
                if self.stop_event.is_set():
                    break

                if not self.check_user_input():
                    break

                self.check_connection()
                self.clear()
                self.draw_connectors()
                self.draw_stations()
                self.draw_carriers()
                self.draw_user_input()
                self.draw_info()
                self.draw_actions()
                self.draw_cursor()

                pygame.display.flip()
            
                self.dt = self.clock.tick(60)/1000
        finally:
            pygame.quit()
            self.stop_event.set()

def start_visualization(connection, stop_event, halt_event):
    visualization = Visualization(connection=connection, stop_event=stop_event, halt_event=halt_event)
    visualization.run()
