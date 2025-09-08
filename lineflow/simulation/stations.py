import pygame
import numpy as np
import simpy
import warnings

from lineflow.helpers import (
    zip_cycle,
    compute_performance_coefficient,
)

from lineflow.simulation.states import (
    TokenState,
    DiscreteState,
    CountState,
    ObjectStates,
    NumericState,
)
from lineflow.simulation.stationary_objects import StationaryObject
from lineflow.simulation.connectors import Buffer
from lineflow.simulation.movable_objects import (
    Part,
    Carrier,
    Worker,
)


class WorkerPool(StationaryObject):

    def __init__(
        self,
        name,
        n_workers=None,
        transition_time=5,
        skill_levels=None,
    ):
        super().__init__()

        assert n_workers is not None, "Workers have to be set"

        self.name = name
        self.n_workers = n_workers
        self.transition_time = transition_time
        self.stations = []
        self._station_names = []
        self._worker_names = [f"W{i}" for i in range(self.n_workers)]
        self.skill_levels = skill_levels or {}
        self.workers = {
            name: Worker(
                name=name,
                transition_time=self.transition_time,
                skill_levels=self.skill_levels.get(name, {})
            ) for name in self._worker_names
        }

    def register_station(self, station):
        self.stations.append(station)
        self._station_names.append(station.name)

    def init_state(self):
        for worker in self.workers.values():
            worker.init_state(self.stations)

        self.state = ObjectStates(
            *[
                worker.state for worker in self.workers.values()
            ]
        )
        # Distribute worker on stations in round robin fashion
        for worker, station in zip_cycle(self.n_workers, self.n_stations):
            self.state[f"W{worker}"].apply(station)

    @property
    def n_stations(self):
        return len(self.stations)

    def register(self, env):
        self.env = env

        for worker in self.workers.values():
            worker.register(env)

        for worker_n, station in zip_cycle(self.n_workers, self.n_stations):

            worker = self.workers[f"W{worker_n}"]
            # Start working
            self.env.process(worker.work())

    def apply(self, actions):
        """
        This should just update the state of the workers
        """
        for worker, station in actions.items():
            worker_obj = self.workers[worker]
            self.env.process(worker_obj.assign(station))

    def get_worker(self, name):
        # gather these workers assigned to these station
        station = self._station_names.index(name)
        requests = {}

        for worker in self.workers.values():
            # If state of worker equals the station, the worker is blocked for exactly this station
            if worker.state.value == station:
                requests[worker.name] = worker
        return requests


class Station(StationaryObject):

    _width = 30
    _height = 30
    _color = 'black'

    def __init__(
        self,
        name,
        position=None,
        processing_time=5,
        processing_std=None,
        rework_probability=0,
        worker_pool=None,
    ):

        super().__init__()

        if position is None:
            position = (0, 0)

        self.name = name
        self.position = pygame.Vector2(position[0], position[1])

        self.worker_pool = worker_pool
        self.worker_requests = {}

        if self.worker_pool is not None:
            self.worker_pool.register_station(self)

        self.processing_time = processing_time
        self.rework_probability = rework_probability

        if self.rework_probability > 1 or self.rework_probability < 0:
            raise ValueError('rework_probability should should be between 0 and 1')

        if processing_std is None:

            self.processing_std = 0.1*self.processing_time
        else:
            assert processing_std >= 0 and processing_std <= 1
            self.processing_std = processing_std*self.processing_time

        self.worker_assignments = {}

    @property
    def is_automatic(self):
        return self.worker_pool is None

    @property
    def n_workers(self):
        if self.worker_pool is not None:
            return len(self.worker_assignments) + 1
        else:
            return 1

    @property
    def worker_skill(self):
        if self.worker_pool is not None:
            skills = [worker.skill_levels.get(self.name, 1.0) for worker in self.worker_assignments.values()]
            skill_sum = np.sum(skills) + 1
            return skill_sum
        else:
            return 1.0

    def setup_draw(self):

        self._rect = pygame.Rect(
            self.position.x - self._width / 2,
            self.position.y - self._height / 2,
            self._width,
            self._height,
        )

        font = pygame.font.SysFont(None, 20)
        self._text = font.render(self.name, True, 'black')

    def _draw(self, screen):
        pygame.draw.rect(screen, self._color, self._rect, border_radius=5)
        self._draw_info(screen)
        screen.blit(
            self._text,
            self._text.get_rect(center=self.position + (0, -0.6 * self._height)),
        )

    def _draw_info(self, screen):
        pass

    def _draw_n_workers(self, screen):
        if not self.is_automatic:
            font = pygame.font.SysFont(None, 14)
            text = font.render(
                "W=" + str(self.worker_skill),
                True,
                'black',
            )
            screen.blit(
                text,
                text.get_rect(center=self.position),
            )

    def _draw_n_carriers(self, screen):
        font = pygame.font.SysFont(None, 14)
        text = font.render(
            "C=" + self.state['carriers_in_magazine'].to_str(),
            True,
            'black',
        )
        screen.blit(
            text,
            text.get_rect(center=self.position),
        )

    def get_performance_coefficient(self):
        return compute_performance_coefficient(self.worker_skill)

    def _sample_exp_time(self, time=None, scale=None, rework_probability=0):
        """
        Samples a time from an exponential distribution
        """

        coeff = self.get_performance_coefficient()
        t = time * coeff + self.random.exponential(scale=scale)

        rework = self.random.choice(
            [1, 2],
            p=[1-rework_probability, rework_probability],
        )

        return t*rework

    def set_to_waiting(self):
        yield self.env.timeout(0)
        self._color = 'yellow'
        self.state['mode'].update('waiting')
        yield self.env.timeout(0)

    def request_workers(self):
        """
        Requests (and blocks) the worker for the process coming up.
        """
        if not self.is_automatic:
            self.worker_assignments = self.worker_pool.get_worker(self.name)

            self.worker_requests = {
                name: worker.request() for name, worker in self.worker_assignments.items()
            }

            # Block workers for this process
            for request in self.worker_requests.values():
                yield request

        else:
            yield self.env.timeout(0)

    def release_workers(self):
        """
        Releases the worker, to they may follow a new assignment
        """
        if not self.is_automatic:

            for worker, request in self.worker_requests.items():
                self.worker_assignments[worker].release(request)
            self.worker_requests = {}
            self.worker_assignments = {}

    def set_to_error(self):
        yield self.env.timeout(0)
        self._color = 'red'
        self.state['mode'].update('failing')
        yield self.env.timeout(0)

    def set_to_work(self):
        yield self.env.timeout(0)
        self._color = 'green'
        self.state['mode'].update('working')
        yield self.env.timeout(0)

    def turn_off(self):
        self._color = 'gray'
        self.state['on'].update(False)
        self.turn_off_event = simpy.Event(self.env)
        return self.turn_off_event

    def is_on(self):
        return self.state['on'].to_str()

    def turn_on(self):
        event = self.turn_off_event

        self.state['on'].update(True)
        if not event.triggered:
            yield event.succeed()
        else:
            yield self.env.timeout(0)

    def connect_to_input(self, station, *args, **kwargs):
        buffer = Buffer(name=f"Buffer_{station.name}_to_{self.name}", *args, **kwargs)
        self._connect_to_input(buffer)
        station._connect_to_output(buffer)

    def connect_to_output(self, station, *args, **kwargs):
        buffer = Buffer(name=f"Buffer_{self.name}_to_{station.name}", *args, **kwargs)
        self._connect_to_output(buffer)
        station._connect_to_input(buffer)

    def _connect_to_input(self, buffer):
        if hasattr(self, 'buffer_in'):
            raise ValueError(f'Input of {self.name} already connected')
        self.buffer_in = buffer.connect_to_output(self)

    def _connect_to_output(self, buffer):
        if hasattr(self, 'buffer_out'):
            raise ValueError(f'Output of {self.name} already connected')
        self.buffer_out = buffer.connect_to_input(self)

    def register(self, env):
        self.env = env
        self.env.process(self.run())

    def _derive_actions_from_new_state(self, state):
        # Turn machine back on if needed
        if not self.is_on() and 'on' in state and hasattr(self, 'turn_off_event') and state['on'] == 0:
            self.env.process(self.turn_on())

    def apply(self, actions):
        self._derive_actions_from_new_state(actions)
        self.state.apply(actions)


class Assembly(Station):
    """
    Assembly takes a carrier from `buffer_in` and `buffer_component`, puts the parts of the component
    carrier on the carrier that came from buffer_in, and pushes that carrier to buffer_out and
    pushes the component carrier to buffer_return if a buffer return exists, otherwise these
    carriers are lost.

    Args:
        name (str): Name of the station
        processing_time (float): Time until parts are moved from component carrier to main carrier
        position (tuple): X and Y position in the visualization
        buffer_return (lineflow.simulation.connectors.Buffer): The buffer to
            put the old component carriers on
        processing_std (float): The standard deviation of the processing time
    """
    def __init__(
        self,
        name,
        buffer_in=None,
        buffer_out=None,
        buffer_component=None,
        processing_time=5,
        position=None,
        buffer_return=None,
        processing_std=None,
        NOK_part_error_time=2,
        worker_pool=None,
    ):

        super().__init__(
            name=name,
            position=position,
            processing_time=processing_time,
            processing_std=processing_std,
            worker_pool=worker_pool,
        )
        self.NOK_part_error_time = NOK_part_error_time

        if buffer_in is not None:
            self._connect_to_input(buffer_in)

        if buffer_out is not None:
            self._connect_to_output(buffer_out)

        if buffer_component is not None:
            self.buffer_component = buffer_component.connect_to_output(self)

        if buffer_return is not None:
            self.buffer_return = buffer_return.connect_to_input(self)

    def init_state(self):
        self.state = ObjectStates(
            DiscreteState('on', categories=[True, False], is_actionable=False, is_observable=False),
            DiscreteState('mode', categories=['working', 'waiting', 'failing']),
            TokenState(name='carrier', is_observable=False),
            TokenState(name='carrier_component', is_observable=False),
            CountState('n_scrap_parts', is_actionable=False, is_observable=True),
            CountState('n_workers', is_actionable=False, is_observable=True, vmin=0),
            NumericState('processing_time', is_actionable=False, is_observable=True, vmin=0),
        )
        self.state['on'].update(True)
        self.state['mode'].update("waiting")
        self.state['carrier'].update(None)
        self.state['carrier_component'].update(None)
        self.state['n_scrap_parts'].update(0)
        self.state['processing_time'].update(self.processing_time)
        self.state['n_workers'].update(self.n_workers)

    def connect_to_component_input(self, station, *args, **kwargs):
        buffer = Buffer(name=f"Buffer_{station.name}_to_{self.name}", *args, **kwargs)
        self.buffer_component = buffer.connect_to_output(self)
        station._connect_to_output(buffer)

    def connect_to_component_return(self, station, *args, **kwargs):
        buffer = Buffer(name=f"Buffer_{self.name}_to_{station.name}", *args, **kwargs)
        self.buffer_return = buffer.connect_to_input(self)
        station._connect_to_input(buffer)

    def _has_invalid_components_on_carrier(self, carrier):
        """
        Checks if any of the components on the carrier is not valid for assembly. In this case,
        `True` is returned. Otherwise, `False` is returned.
        """
        for component in carrier:
            if not component.is_valid_for_assembly(self.name):
                return True
        return False

    def _draw_info(self, screen):
        self._draw_n_workers(screen)

    def run(self):

        while True:
            if self.is_on():

                yield self.env.process(self.request_workers())
                self.state['n_workers'].update(self.n_workers)
                # Wait to get part from buffer_in
                yield self.env.process(self.set_to_waiting())
                carrier = yield self.env.process(self.buffer_in())

                # Update current_carrier and count parts of carrier
                self.state['carrier'].update(carrier.name)

                # Run until carrier with components each having a valid assembly condition is
                # received
                while True:
                    # Wait to get component
                    carrier_component = yield self.env.process(self.buffer_component())
                    self.state['carrier_component'].update(carrier_component.name)

                    # Check component
                    if self._has_invalid_components_on_carrier(carrier_component):
                        yield self.env.process(self.set_to_error())
                        yield self.env.timeout(self.NOK_part_error_time)
                        self.state['n_scrap_parts'].increment()

                        # send carrier back
                        if hasattr(self, 'buffer_return'):
                            carrier_component.parts.clear()
                            yield self.env.process(self.buffer_return(carrier_component))
                        yield self.env.process(self.set_to_waiting())
                        continue

                    else:
                        # All components are valid, proceed with assembly
                        break

                # Process components
                yield self.env.process(self.set_to_work())
                processing_time = self._sample_exp_time(
                    time=self.processing_time + carrier.get_additional_processing_time(self.name),
                    scale=self.processing_std,
                )
                yield self.env.timeout(processing_time)
                self.state['processing_time'].update(processing_time)

                for component in carrier_component:
                    carrier.assemble(component)

                # Release workers
                self.release_workers()

                # Place carrier on buffer_out
                yield self.env.process(self.set_to_waiting())
                yield self.env.process(self.buffer_out(carrier))
                self.state['carrier'].update(None)

                # send component carrier back
                if hasattr(self, 'buffer_return'):
                    yield self.env.process(self.buffer_return(carrier_component))

                self.state['carrier_component'].update(None)

            else:
                yield self.turn_off()


class Process(Station):
    '''
    Process stations take a carrier as input, process the carrier, and push it onto buffer_out
    Args:
        processing_std: Standard deviation of the processing time
        rework_probability: Probability of a carrier to be reworked (takes 2x the time)
        position (tuple): X and Y position in visualization
    '''

    def __init__(
        self,
        name,
        buffer_in=None,
        buffer_out=None,
        processing_time=5,
        position=None,
        processing_std=None,
        rework_probability=0,
        worker_pool=None,

    ):

        super().__init__(
            name=name,
            position=position,
            processing_time=processing_time,
            processing_std=processing_std,
            rework_probability=rework_probability,
            worker_pool=worker_pool,
        )

        if buffer_in is not None:
            self._connect_to_input(buffer_in)

        if buffer_out is not None:
            self._connect_to_output(buffer_out)

    def init_state(self):

        self.state = ObjectStates(
            DiscreteState('on', categories=[True, False], is_actionable=False, is_observable=False),
            DiscreteState('mode', categories=['working', 'waiting', 'failing']),
            TokenState(name='carrier', is_observable=False),
            NumericState('processing_time', is_actionable=False, is_observable=True, vmin=0),
            CountState('n_workers', is_actionable=False, is_observable=True, vmin=0),
        )
        self.state['on'].update(True)
        self.state['mode'].update("waiting")
        self.state['carrier'].update(None)
        self.state['processing_time'].update(self.processing_time)
        self.state['n_workers'].update(self.n_workers)

    def _draw_info(self, screen):
        self._draw_n_workers(screen)

    def run(self):

        while True:
            if self.is_on():
                yield self.env.process(self.request_workers())
                self.state['n_workers'].update(self.n_workers)
                # Wait to get part from buffer_in
                yield self.env.process(self.set_to_waiting())
                carrier = yield self.env.process(self.buffer_in())
                self.state['carrier'].update(carrier.name)

                yield self.env.process(self.set_to_work())

                processing_time = self._sample_exp_time(
                    time=self.processing_time + carrier.get_additional_processing_time(self.name),
                    scale=self.processing_std,
                    rework_probability=self.rework_probability,
                )
                yield self.env.timeout(processing_time)
                self.state['processing_time'].update(processing_time)

                # Release workers
                self.release_workers()

                # Wait to place carrier to buffer_out
                yield self.env.process(self.set_to_waiting())
                yield self.env.process(self.buffer_out(carrier))
                self.state['carrier'].update(None)

            else:
                yield self.turn_off()


class Source(Station):
    '''
    Source station generating parts on carriers.

    The Source takes carriers from buffer_in, creates a part, places that part
    onto the carrier, and pushes the carrier onto the buffer_out.
    If unlimited carriers is True, no buffer_in is needed and no magazine.

    Args:
        name (str): Name of the Cell
        carrier_specs (dict): Nested dict. Top level descripes carrier types, each consists of a
            dict specifying different parts setup on the carrier at the source. The part level
            specifies how the part behaves at future processes along the layout. For instance a spec
            `{'C': {'Part1': {'Process1': {'assembly_condition': 5}, 'Process2': {'extra_processing_time': 10}}}}` 
            tells that the produced carrier has one part `Part1` that has to fullfill an assembly condition of `5` 
            at station `Process1` and gets an additional processing time of `10` at `Process2`.
        buffer_in (lineflow.simulation.connectors.Buffer, optional): Buffer in
        buffer_out (obj): Buffer out
        processing_time (float): Time it takes to put part on carrier (carrier needs to be
            available)
        processing_std (float): Standard deviation of processing time
        waiting_time (float): Time to wait between pushing a carrier out and taking the next one
        position (tuple): X and Y position in visualization
        unlimited_carriers (bool): If source has the ability to create unlimited carriers
        carrier_capacity (int): Defines how many parts can be assembled on a carrier. If set to
            default (infinity) or > 15, carrier will be visualized with one part.
        carrier_min_creation (int): Minimum number of carriers of same spec created subsequentially
        carrier_max_creation (int): Maximum number of carriers of same spec created subsequentially

    '''
    def __init__(
        self,
        name,
        buffer_in=None,
        buffer_out=None,
        processing_time=2,
        processing_std=None,
        waiting_time=0,
        waiting_time_step=0.5,
        position=None,
        actionable_magazin=True,
        actionable_waiting_time=True,
        unlimited_carriers=False,
        carrier_capacity=np.inf,
        carrier_specs=None,
        carrier_min_creation=1,
        carrier_max_creation=None,
    ):
        super().__init__(
            name=name,
            position=position,
            processing_time=processing_time,
            processing_std=processing_std,
        )
        self._assert_init_args(unlimited_carriers, carrier_capacity, buffer_in)

        if buffer_in is not None:
            self._connect_to_input(buffer_in)
        if buffer_out is not None:
            self._connect_to_output(buffer_out)

        self.buffer_in_object = buffer_in
        self.unlimited_carriers = unlimited_carriers
        self.carrier_capacity = carrier_capacity
        self.waiting_time_step = waiting_time_step

        self.actionable_magazin = actionable_magazin
        self.actionable_waiting_time = actionable_waiting_time

        if carrier_specs is None:
            carrier_specs = {"carrier": {"part": {}}}
        self.carrier_specs = carrier_specs

        self.unlimited_carriers = unlimited_carriers
        self.carrier_capacity = carrier_capacity
        self.carrier_id = 1
        self.carrier_min_creation = carrier_min_creation
        self.carrier_max_creation = carrier_max_creation if carrier_max_creation is not None else 2*carrier_min_creation

        self._carrier_counter = 0

        self.init_waiting_time = waiting_time

    def init_state(self):

        self.state = ObjectStates(
            DiscreteState('on', categories=[True, False], is_actionable=False, is_observable=False),
            DiscreteState('mode', categories=['working', 'waiting', 'failing']),
            DiscreteState(
                name='waiting_time', 
                categories=np.arange(0, 100, self.waiting_time_step), 
                is_actionable=self.actionable_waiting_time,
            ),
            TokenState(name='carrier', is_observable=False),
            TokenState(name='part', is_observable=False),
            DiscreteState(
                name='carrier_spec', 
                categories=list(self.carrier_specs.keys()), 
                is_actionable=False,
                is_observable=True,
            ),
        )

        self.state['waiting_time'].update(self.init_waiting_time)
        self.state['on'].update(True)
        self.state['mode'].update("waiting")
        self.state['carrier'].update(None)
        self.state['part'].update(None)
        self.state['carrier_spec'].update(list(self.carrier_specs.keys())[0])

    def _assert_init_args(self, unlimited_carriers, carrier_capacity, buffer_in):
        if unlimited_carriers:
            if carrier_capacity > 15:
                warnings.warn(
                    "If carrier_capacity > 15, visualization of parts"
                    "on carriers is restriced and carrier will be visualized with one part")
            if not isinstance(carrier_capacity, int) and carrier_capacity != np.inf:
                raise AttributeError("Type of carrier capacity must be int or np.inf")

    def create_carrier(self):

        if self._carrier_counter == 0:
            carrier_spec = self.random.choice(list(self.carrier_specs.keys()))
            self.state['carrier_spec'].update(carrier_spec)
            self._carrier_counter = self.random.randint(
                self.carrier_min_creation, 
                self.carrier_max_creation + 1,
            )

        carrier_spec = self.state['carrier_spec'].to_str()

        name = f'{self.name}_{carrier_spec}_{self.carrier_id}'
        carrier = Carrier(
            self.env, 
            name=name, 
            capacity=self.carrier_capacity, 
            part_specs=self.carrier_specs[carrier_spec],
        )
        self.carrier_id += 1
        self._carrier_counter -= 1

        return carrier

    def create_parts(self, carrier):
        """
        Creates the parts based on the part_specs attribute
        For each dict in the part_specs list one part is created
        """

        parts = []
        for part_id, (part_name, part_spec) in enumerate(carrier.part_specs.items()):
            part = Part(
                env=self.env,
                name=f"{carrier.name}_{part_name}_{part_id}",
                specs=part_spec,
            )
            part.create(self.position)
            parts.append(part)
        return parts

    def assemble_parts_on_carrier(self, carrier, parts):
        """
        Put parts onto carrier
        """
        for part in parts:
            carrier.assemble(part)

    def assemble_carrier(self, carrier):

        parts = self.create_parts(carrier)
        self.state['part'].update(parts[0].name)

        processing_time = self._sample_exp_time(
            time=self.processing_time,
            scale=self.processing_std,
        )
        self.state['carrier'].update(carrier.name)

        yield self.env.timeout(processing_time)
        self.assemble_parts_on_carrier(carrier, parts)

        return carrier

    def wait(self):

        waiting_time = self.state['waiting_time'].to_str()

        if waiting_time > 0:
            yield self.env.process(self.set_to_waiting())
            yield self.env.timeout(waiting_time)

    def run(self):

        while True:
            if self.is_on():
                yield self.env.process(self.set_to_waiting())
                yield self.env.process(self.wait())

                if self.unlimited_carriers:
                    carrier = self.create_carrier()
                else:
                    carrier = yield self.env.process(self.buffer_in())

                yield self.env.process(self.set_to_work())
                carrier = yield self.env.process(self.assemble_carrier(carrier))

                yield self.env.process(self.set_to_waiting())
                yield self.env.process(self.buffer_out(carrier))
                self.state['part'].update(None)
                self.state['carrier'].update(None)

            else:
                yield self.turn_off()


class Sink(Station):
    """
    The Sink takes carriers from buffer_in. It removes the parts of the carrier and either
    destroys it or puts them to buffer_out if one exists.

    Args:
        processing_std (float): The standard deviation of the processing time.
        position (tuple): X and Y position in the visualization.
    """
    def __init__(
        self,
        name,
        buffer_in=None,
        buffer_out=None,
        processing_time=2,
        processing_std=None,
        position=None,
    ):
        super().__init__(
            name=name,
            processing_time=processing_time,
            processing_std=processing_std,
            position=position,
        )

        if buffer_in is not None:
            self._connect_to_input(buffer_in)
        if buffer_out is not None:
            self._connect_to_output(buffer_out)

    def init_state(self):

        self.state = ObjectStates(
            DiscreteState('on', categories=[True, False], is_actionable=False, is_observable=False),
            DiscreteState('mode', categories=['working', 'waiting', 'failing']),
            CountState('n_parts_produced', is_actionable=False, is_observable=False),
            TokenState(name='carrier', is_observable=False),
        )

        self.state['on'].update(True)
        self.state['mode'].update("waiting")
        self.state['n_parts_produced'].update(0)
        self.state['mode'].update("waiting")
        self.state['carrier'].update(None)

    def remove(self, carrier):

        processing_time = self._sample_exp_time(
            time=self.processing_time,
            scale=self.processing_std,
        )
        yield self.env.timeout(processing_time)
        self.state['n_parts_produced'].increment()

        if hasattr(self, 'buffer_out'):
            yield self.env.process(self.set_to_waiting())
            carrier.parts.clear()
            yield self.env.process(self.buffer_out(carrier))

    def run(self):

        while True:
            if self.is_on():
                yield self.env.process(self.set_to_waiting())
                carrier = yield self.env.process(self.buffer_in())
                yield self.env.process(self.set_to_work())
                self.state['carrier'].update(carrier.name)

                # Wait to place carrier to buffer_out
                yield self.env.process(self.remove(carrier))
                self.state['carrier'].update(None)

            else:
                yield self.turn_off()


class Switch(Station):
    """
    A Switch distributes carriers onto buffer outs. In and out buffers can be provided to
    the constructor but can also be added to a switch using the `connect_to_input` and `connect_to_output`
    methods.

    Args:
        buffers_in (list): A list of buffers that lead into the Switch.
        buffers_out (list): A list of buffers that lead away from the Switch.
        position (tuple): X and Y position in the visualization.
        alternate (bool): If True, the Switch switches between the buffers_out; else, only one buffer_out is used.
    """

    def __init__(
        self,
        name,
        buffers_in=None,
        buffers_out=None,
        position=None,
        processing_time=5,
        alternate=False,
    ):
        super().__init__(
            name=name,
            position=position,
            processing_time=processing_time,
            # We assume switches do not have variation here
            processing_std=0,
        )

        # time it takes for a model to change buffer_in or buffer_out
        self.readjustment_time = 10

        self.buffer_in = []
        self.buffer_out = []

        if buffers_in is not None:
            for buffer in buffers_in:
                self._connect_to_input(buffer)

        if buffers_out is not None:
            for buffer in buffers_out:
                self._connect_to_output(buffer)

        self.alternate = alternate

    def init_state(self):
        self.state = ObjectStates(
            DiscreteState('on', categories=[True, False], is_actionable=False, is_observable=False),
            DiscreteState('mode', categories=['working', 'waiting', 'failing']),
            DiscreteState(
                name='index_buffer_in',
                categories=list(range(self.n_buffers_in)),
                is_actionable=not self.alternate and self.n_buffers_in > 1
            ),
            DiscreteState(
                name='index_buffer_out',
                categories=list(range(self.n_buffers_out)),
                is_actionable=not self.alternate and self.n_buffers_out > 1),
            TokenState(name='carrier', is_observable=False),
        )
        self.state['index_buffer_in'].update(0)
        self.state['index_buffer_out'].update(0)
        self.state['on'].update(True)
        self.state['mode'].update("waiting")
        self.state['carrier'].update(None)

    @property
    def n_buffers_in(self):
        return len(self.buffer_in)

    @property
    def n_buffers_out(self):
        return len(self.buffer_out)

    def _get_buffer_in_position(self):
        return self.buffer_in[
            self.state['index_buffer_in'].value
        ].__self__._positions_slots[-1]

    def _get_buffer_out_position(self):
        return self.buffer_out[
            self.state['index_buffer_out'].value
        ].__self__._positions_slots[0]

    def _draw_info(self, screen):
        pos_buffer_in = self._get_buffer_in_position()
        pos_buffer_out = self._get_buffer_out_position()

        pos_in = pos_buffer_in + 0.5*(self.position - pos_buffer_in)
        pos_out = pos_buffer_out + 0.5*(self.position - pos_buffer_out)

        pygame.draw.circle(screen, 'gray', self.position, 6)
        for pos in [pos_in, pos_out]:
            pygame.draw.line(screen, "gray", self.position, pos, width=5)

    def _connect_to_input(self, buffer):
        self.buffer_in.append(buffer.connect_to_output(self))

    def _connect_to_output(self, buffer):
        self.buffer_out.append(buffer.connect_to_input(self))

    def _alternate_indices(self):
        self.state['index_buffer_in'].set_next()
        self.state['index_buffer_out'].set_next()

    def look_in(self):
        """
        Checks if part at current buffer_in is available
        """
        buffer_in = self.buffer_in[self.state['index_buffer_in'].value].__self__
        while buffer_in.get_fillstate() == 0:
            yield self.env.timeout(1)
            buffer_in = self.buffer_in[self.state['index_buffer_in'].value].__self__
        return buffer_in

    def look_out(self):
        """
        Checks if space at current buffer_out is available
        """
        buffer_out = self.buffer_out[self.state['index_buffer_out'].value].__self__

        while buffer_out.get_fillstate() == 1:
            yield self.env.timeout(1)
            # check if buffer out changed
            buffer_out = self.buffer_out[self.state['index_buffer_out'].value].__self__
        return buffer_out

    def get(self):
        while True:
            yield self.env.process(self.set_to_waiting())
            buffer_in = yield self.env.process(self.look_in())
            self.getting_process = None
            yield self.env.process(self.set_to_work())
            carrier = yield self.env.process(
                buffer_in.get()
            )
            self.state['carrier'].update(carrier.name)
            return carrier

    def put(self, carrier):
        while True:
            yield self.env.process(self.set_to_waiting())
            buffer_out = yield self.env.process(self.look_out())
            yield self.env.process(buffer_out.put(carrier))
            self.state['carrier'].update(None)
            return

    def run(self):
        while True:
            if self.is_on():
                # Get carrier
                carrier = yield self.env.process(self.get())

                # Process
                yield self.env.process(self.set_to_work())
                yield self.env.timeout(self.processing_time)

                yield self.env.process(self.put(carrier))

                if self.alternate:
                    self._alternate_indices()

            else:
                yield self.turn_off()


class Magazine(Station):
    '''
    Magazine station manages carriers.

    The Magazine gets carriers from buffer_in and stores them in the
    magazine. Afterwards it takes a carrier from its magazine and pushes the
    carrier to buffer_out.
    If unlimited_carriers is True no buffer_in is needed.

    Args:
        unlimited_carriers (bool): If True, the Magazine will have an unlimited amount of carriers available
        carriers_in_magazine (int): Number of carriers in the magazine
        carrier_getting_time (float): Time to get a carrier from the magazine
        actionable_magazine (bool): If True, carriers in the magazine is in an actionable state
        carrier_capacity (int): Defines how many parts can be assembled on a carrier. If set to default (infinity) or > 15, carrier will be visualized with one part.
    '''
    def __init__(
        self,
        name,
        buffer_in=None,
        buffer_out=None,
        position=None,
        unlimited_carriers=True,
        carrier_capacity=np.inf,
        actionable_magazine=True,
        carrier_getting_time=2,
        carriers_in_magazine=0,
        carrier_specs=None,
        carrier_min_creation=1,
        carrier_max_creation=None,
    ):
        super().__init__(
            name=name,
            position=position,
        )
        self._assert_init_args(buffer_in, unlimited_carriers, carriers_in_magazine, carrier_capacity)

        if buffer_in is not None:
            self._connect_to_input(buffer_in)
        if buffer_out is not None:
            self._connect_to_output(buffer_out)

        self.actionable_magazine = actionable_magazine
        self.init_carriers_in_magazine = carriers_in_magazine
        self.carrier_getting_time = carrier_getting_time

        if carrier_specs is None:
            carrier_specs = {"carrier": {"part": {}}}
        self.carrier_specs = carrier_specs

        self.unlimited_carriers = unlimited_carriers
        self.carrier_capacity = carrier_capacity
        self.carrier_id = 1
        self.carrier_min_creation = carrier_min_creation
        self.carrier_max_creation = carrier_max_creation if carrier_max_creation is not None else 2*carrier_min_creation
        self._carrier_counter = 0

    def init_state(self):

        self.state = ObjectStates(
            DiscreteState('on', categories=[True, False], is_actionable=False, is_observable=False),
            DiscreteState('mode', categories=['working', 'waiting', 'failing']),
            CountState('carriers_in_magazine', is_actionable=self.actionable_magazine, is_observable=True),
            TokenState(name='carrier', is_observable=False),
            TokenState(name='part', is_observable=False),
        )

        self.state['carriers_in_magazine'].update(self.init_carriers_in_magazine)
        self.state['on'].update(True)
        self.state['mode'].update("waiting")
        self.state['carrier'].update(None)
        self.state['part'].update(None)

    def _assert_init_args(self, buffer_in, unlimited_carriers, carriers_in_magazine, carrier_capacity):
        if carrier_capacity > 15:
            warnings.warn("If carrier_capacity > 15, visualization of parts on carriers is restriced and carrier will be visualized with one part")

        if not isinstance(carrier_capacity, int) and carrier_capacity != np.inf:
            raise AttributeError("Type of carrier capacity must be int or np.inf")

        if not unlimited_carriers and carriers_in_magazine == 0:
            raise AttributeError(f"unlimited_carriers is {unlimited_carriers} and cell also has 0 carriers in magazine")

        if unlimited_carriers and carriers_in_magazine > 0:
            raise AttributeError(f"unlimited_carriers is {unlimited_carriers} and cell has more than 0 carriers in magazine")

        if buffer_in and unlimited_carriers:
                raise AttributeError(f"Only magazine or unlimited_carriers {unlimited_carriers} is required")

    def create_carrier(self):
        if self._carrier_counter == 0:
            self._current_carrier_spec = self.random.choice(list(self.carrier_specs.keys()))
            self._carrier_counter = self.random.randint(
                self.carrier_min_creation, 
                self.carrier_max_creation + 1,
            )

        name = f'{self.name}_{self._current_carrier_spec}_{self.carrier_id}'
        carrier = Carrier(
            self.env, 
            name=name, 
            capacity=self.carrier_capacity, 
            part_specs=self.carrier_specs[self._current_carrier_spec],
        )
        self.carrier_id += 1
        self._carrier_counter -= 1

        return carrier

    def _initial_fill_magazine(self, n_carriers):
        # attribute needs to be set here as env is not available in __init__()
        self.magazine = simpy.Store(self.env)
        for i in range(n_carriers):
            carrier = self.create_carrier()
            self.magazine.put(carrier)

    def get_carrier_from_magazine(self):
        yield self.env.process(self._update_magazine())
        yield self.env.timeout(self.carrier_getting_time)

        while True:
            yield self.env.process(self._update_magazine())
            yield self.env.process(self.set_to_work())
            if len(self.magazine.items) > 0:
                carrier = yield self.magazine.get()
                break
            else:
                yield self.env.process(self.set_to_waiting())
                yield self.env.timeout(1)

        self.state['carriers_in_magazine'].decrement()
        return carrier

    def _buffer_in_to_magazine(self):
        while True:
            carrier = yield self.env.process(self.buffer_in())
            yield self.env.process(self.add_carrier_to_magazine(carrier))

    def add_carrier_to_magazine(self, carrier):
        yield self.magazine.put(carrier)
        self.state['carriers_in_magazine'].increment()

    def _update_magazine(self):
        '''
        update the magazine according to state
        '''
        should = self.state['carriers_in_magazine'].value
        current = len(self.magazine.items)
        diff = should - current
        if diff > 0:
            for i in range(diff):
                carrier = self.create_carrier()
                self.magazine.put(carrier)

        if diff < 0:
            for i in range(abs(diff)):
                carrier = yield self.magazine.get()

    def _draw_info(self, screen):
        self._draw_n_carriers(screen)

    def get_carrier(self):
        # First check if Magazine is allowed to create unlimited carriers
        if self.unlimited_carriers:
            yield self.env.timeout(self.carrier_getting_time)
            carrier = self.create_carrier()

        # Second check magazine
        else:
            carrier = yield self.env.process(self.get_carrier_from_magazine())
        self.state["carrier"].update(carrier.name)
        return carrier

    def run(self):
        # Initially fill the magazine with carriers
        self._initial_fill_magazine(self.state['carriers_in_magazine'].value)

        if hasattr(self, 'buffer_in'):
            self.env.process(self._buffer_in_to_magazine())

        while True:
            if self.is_on():
                # Get carrier from Magazine
                yield self.env.process(self.set_to_work())
                carrier = yield self.env.process(self.get_carrier())

                # Wait to place carrier to buffer_out
                yield self.env.process(self.set_to_waiting())
                yield self.env.process(self.buffer_out(carrier))
                self.state['carrier'].update(None)
            else:
                yield self.turn_off()
