import pygame
import numpy as np
from simpy import (
    Store,
    Resource,
)

from lineflow.simulation.states import DiscreteState


class MovableObject(object):

    def __init__(self, env, name, specs=None):

        if specs is None:
            specs = {}
        self.specs = specs.copy()

        self.specs["creation_time"] = env.now
        self.specs["name"] = name
        self.env = env
        self._position = None

    @property
    def name(self):
        return self['name']

    @property
    def creation_time(self):
        return self['creation_time']

    def draw(self, screen, with_text=True):

        self._draw_shape(screen)
        if with_text:
            font = pygame.font.SysFont(None, 12)
            text = font.render(self.name, True, 'blue')
            screen.blit(text, text.get_rect(center=self._position + (0, -1.3*self._height)))

    def _draw_shape(self, screen):
        raise NotImplementedError()

    def move(self, position):
        if not isinstance(position, pygame.Vector2):
            raise ValueError('Expect pygame vector as position')

        self._position = position

    def __getitem__(self, name):
        return self.specs[name]

    def __setitem__(self, name, value):
        self.specs[value] = name


class Worker(object):
    def __init__(self, name, transition_time=5, skill_levels=None):
        self.name = name
        self.transition_time = transition_time
        self.skill_levels = skill_levels

    def register(self, env):
        self.env = env
        self._working = Resource(self.env, capacity=1)
        self.assignment = Store(env=self.env, capacity=1)

    def release(self, request):
        self._working.release(request)

    def request(self):
        return self._working.request()
    
    def get_skill_level(self, station_name):
        return self.skill_levels.get(station_name, 1.0)

    def assign(self, station):
        """
        Assign worker to station.

        """
        if len(self.assignment.items) > 0:
            # Clean old assignment
            yield self.assignment.get()

        yield self.assignment.put(station)

    def init_state(self, stations):

        self.stations = stations
        self.state = DiscreteState(
            name=self.name,
            categories=[s.name for s in self.stations],
            is_observable=True,
            is_actionable=True,
        )

    def work(self):

        # Initially fill value of state to assignment
        yield self.assignment.put(self.state.value)

        while True:
            # Wait for new assignment
            station = yield self.assignment.get()

            # Wait until worker is released from current station
            transition_request = self.request()
            yield transition_request

            if self.state.value != station:
                # New cell-assignment, wait for transition
                # Move to new cell
                yield self.env.timeout(self.transition_time)

            self.release(transition_request)
            # Station now can create requests
            self.state.apply(station)


class Part(MovableObject):
    def __init__(self, env, name, specs=None, color='Orange'):
        super(Part, self).__init__(env, name, specs=specs)
        self._color = color

    def is_valid_for_assembly(self, station_name):
        """
        If the part has an `assembly_condition` in its specification, then it checks whether the
        time between its creation and now is smaller than this condition. Otherwise it will just
        return true.
        """
        if "assembly_condition" in self.specs.get(station_name, {}):
            return (self.env.now - self["creation_time"]) < self.specs[station_name]["assembly_condition"]
        else:
            return True

    def create(self, position):
        if not isinstance(position, pygame.Vector2):
            raise ValueError('Expect pygame vector as position')
        self.move(position)

    def _draw(self, screen, x, y, width, height):
        _part_rect = pygame.Rect(x, y, width, height)
        pygame.draw.rect(screen, self._color, _part_rect, border_radius=1)


class Carrier(MovableObject):

    def __init__(self, env, name, color='Black', width=30, height=10, capacity=np.inf, part_specs=None):
        super(Carrier, self).__init__(env, name, specs=None)
        self.capacity = capacity
        self._color = color
        self._width = width
        self._height = height

        if part_specs is None:
            part_specs = {}
        self.part_specs = part_specs.copy()

        self._width_part = 0.8*self._width
        if capacity < 15:
            self._width_part = self._width_part / self.capacity

        self._height_part = 0.7*self._height

        self.parts = {}

    def assemble(self, part):

        if part.name in self.parts:
            raise ValueError(f'A part with name {part.name} already contained')

        if not hasattr(part, "creation_time"):
            raise ValueError('Part not created')

        if self.capacity == len(self.parts):
            raise ValueError('Carrier is already full. Check your carrier_capacity')

        self.parts[part.name] = part

    def _draw_shape(self, screen):

        self._rect = pygame.Rect(
            self._position.x - self._width / 2,
            self._position.y - self._height / 2,
            self._width,
            self._height,
        )
        pygame.draw.rect(screen, self._color, self._rect, border_radius=2)

        for i, part in enumerate(self):
            part._draw(
                screen,
                x=self._position.x+0.1*self._width - self._width / 2 + i*(self._width_part),
                y=self._position.y - self._height_part / 2,
                width=self._width_part,
                height=self._height_part,
            )

    def move(self, position):
        """
        """

        # If no position has been given, no move is taking place
        if position is None:
            return

        if not isinstance(position, pygame.Vector2):
            raise ValueError('Expect pygame vector as position')

        self._position = position

        for part in self.parts.values():
            part.move(position)

    def __iter__(self):
        for part in self.parts.values():
            yield part

    def get_additional_processing_time(self, station):
         total_time = 0

         for part in self:
             processing_time = part.specs.get(station, {}).get("extra_processing_time", 0)
             total_time += processing_time

         return total_time



