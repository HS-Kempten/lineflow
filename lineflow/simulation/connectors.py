import numpy as np
import simpy
import pygame

from lineflow.simulation.stationary_objects import StationaryObject
from lineflow.simulation.states import (
    ObjectStates,
    NumericState,
    DiscreteState,
)


class Connector(StationaryObject):
    _position_input = None
    _position_output = None

    def put(self):
        raise NotImplementedError()

    def get(self):
        raise NotImplementedError()

    def connect_to_input(self, station):
        self._position_input = station.position
        return self.put

    def connect_to_output(self, station):
        self._position_output = station.position
        return self.get

    def setup_positions(self):
        raise NotImplementedError()


class Buffer(Connector):
    """
    Element that connects two different types of stations.

    Args:
        name (str): Name of the station
        capacity (int): Number of slots the buffer can hold
        transition_time (float): Time carriers need to traverse the full buffer
        put_time (float): Time the buffer needs to hand over a carrier to the next element
        get_time (float): Time the buffer needs to get a carrier to the previous element

    """

    def __init__(self, name, capacity=2, transition_time=10, put_time=1, get_time=1, put_std=None):
        super().__init__()
        self.name = name
        self.transition_time_between_slots = transition_time / (capacity - 1)
        self.transition_time = transition_time
        self.put_time = put_time
        self.get_time = get_time
        self.color = "gray"

        # Small registry of carriers
        self.carriers = {}
        self.capacity = capacity

        if put_std is None:
            self.put_std = 0.1*self.put_time
        else:
            self.put_std = put_std

        self._positions_slots = self.capacity * [None]
        self._positions_arrow = self.capacity * [None]

    def init_state(self):

        self.state = ObjectStates(
            DiscreteState('on', categories=[True, False], is_actionable=False, is_observable=False),
            NumericState(name='fill', vmin=0, vmax=1, is_observable=True, is_actionable=False),
        )

        self.state['on'].update(True)
        self.state['fill'].update(0)

    @property
    def n_carriers(self):
        return len(self.carriers)

    def setup_positions(self):

        vec_direction = np.array(
            [
                self._position_output.x - self._position_input.x,
                self._position_output.y - self._position_input.y
            ]
        ) / (self.capacity + 1)

        if vec_direction[0] == 0 and vec_direction[1] == 0:
            raise ValueError(f'Start and end position of {self.name} equal!')

        vec_start = np.array([self._position_input.x, self._position_input.y])

        for i in range(self.capacity):

            pos = vec_start + (i+1)*vec_direction
            self._positions_slots[i] = pygame.Vector2(pos[0], pos[1])

        # Calculate arrowhead points
        arrowhead_size = 3.5
        vec_normalized = vec_direction / np.linalg.norm(vec_direction)

        for i in range(self.capacity):
            positions_arrow = vec_start + (i+1.55) * vec_direction
            arrowhead = np.tile(positions_arrow, (3, 1))

            for j, index in enumerate([0, 2]):
                arrowhead[index] += arrowhead_size*np.array(
                    [
                        -vec_normalized[0]+(-1)**j*vec_normalized[1],
                        -vec_normalized[1]-(-1)**j*vec_normalized[0],
                    ]
                )

            self._positions_arrow[i] = arrowhead
            
    def _add(self, data_list):
        data_list.append(dict(type='connector',start=self._position_input,end=self._position_output,n_slots=self.capacity))
        for carrier in self.carriers.values():
            carrier._add(data_list)

    def _sample_put_time(self):
        return self.put_time + self.random.exponential(scale=self.put_std)

    def get(self):
        self.carrier = yield self.slots[-1].get()
        # Release segment
        yield self.blockers[-1].get()

        # Remove carrier from registry
        self.carriers.pop(self.carrier.name)
        self.state['fill'].update(self.get_fillstate())
        yield self.env.timeout(self.get_time)
        return self.carrier

    def put(self, carrier):

        # Wait for segment to be released
        yield self.blockers[0].put(1)

        # Wait a bit to actually put part
        yield self.env.timeout(self._sample_put_time())

        yield self.slots[0].put(carrier)

        carrier.move(self._positions_slots[0])

        # Remove carrier from registry
        self.carriers[carrier.name] = carrier
        self.state['fill'].update(self.get_fillstate())

    def get_fillstate(self):
        return self.n_carriers/self.capacity

    def _move(self, i):

        slot_from = self.slots[i]
        slot_to = self.slots[i+1]

        blocker_self = self.blockers[i]
        blocker_next = self.blockers[i+1]

        while True:
            # Wait for carrier in slot
            carrier = yield slot_from.get()

            # Waiting for segment to be free
            yield blocker_next.put(1)

            carrier.move(self._positions_slots[i+1])

            # Release segment before
            yield blocker_self.get()

            # Start moving Transition
            yield self.env.timeout(self.transition_time_between_slots)

            # Push carrier to next segment
            yield slot_to.put(carrier)

    def register(self, env):
        self.env = env

        self.slots = [
            simpy.Store(
                env=self.env,
                capacity=1,
            ) for _ in range(self.capacity)
        ]

        self.blockers = [
            simpy.Store(
                env=self.env,
                capacity=1,
            ) for _ in range(self.capacity)
        ]

        for i in range(self.capacity - 1):
            self.env.process(self._move(i))
