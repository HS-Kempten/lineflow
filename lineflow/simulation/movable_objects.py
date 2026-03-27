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

    def get_visualization_data(self):
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

        if skill_levels is None:
            skill_levels = {}
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
    def __init__(self, env, name, specs=None, color='Orange', nok_probability=0.0):
        super(Part, self).__init__(env, name, specs=specs)
        self.nok_probability = nok_probability
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

    def get_processing_time(self, station):
        return self.specs.get(station, {}).get("extra_processing_time", 0)

    def get_error_probability(self, station):
        return self.specs.get(station, {}).get("error_probability", 0.0)

    def get_error_time(self, station):
        return self.specs.get(station, {}).get("error_time", 0)


class Carrier(MovableObject):

    def __init__(self, env, name, color='Black', width=30, height=10, capacity=np.inf):
        super(Carrier, self).__init__(env, name, specs=None)
        self.capacity = capacity
        self._color = color
        self._width = width
        self._height = height

        self._width_part = 0.8*self._width
        if capacity < np.inf:
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

    def get_visualization_data(self, with_text=True):
        parts = len(self.parts)
        if np.isinf(self.capacity) and parts != 0:
            fill = 1
        else:
            fill = parts/self.capacity

        data = dict(type='carrier', position=self._position, fill=fill)

        if with_text:
            data['name'] = self.name
        return data

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

    def get_parts_for_station(self, station):
        return [p for p in self if station in p.specs]

    def get_additional_processing_time(self, station):
         total_time = 0

         for part in self:
             processing_time = part.specs.get(station, {}).get("extra_processing_time", 0)
             total_time += processing_time

         return total_time
