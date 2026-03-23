import unittest
from lineflow.simulation.movable_objects import (
    Carrier, 
    Part,
)
from lineflow.simulation import (
    WorkerPool,
    Source,
    Sink,
    Line,
    SequentialProcess,
)


carrier_specs = {
    'Type_A': {
        'Part1': {
            'Process1': {
                'extra_processing_time': 20,
                'error_probability': 0.0,
                'error_time': 0,
            }, 
            'Process2': {
                'extra_processing_time': 0,
                'error_probability': 0.0,
                'error_time': 0,
                }
        },
        'Part2': {
            'Process2': {
                'extra_processing_time': 10,
                'error_probability': 0.5,
                'error_time': 10,
            }
        }
    },
    'Type_B': {
        'Part1': {
            'Process1': {
                'extra_processing_time': 0,
                'error_probability': 0.0,
                'error_time': 0,
    
                }, 
            'Process2': {
                'extra_processing_time': 20,
                'error_probability': 0.5,
                'error_time': 10,
            }
        },
        'Part2': {
            'Process1': {
                'extra_processing_time': 10,
                'error_probability': 0.0,
                'error_time': 0,
            }, 
            'Process2': {
                'extra_processing_time': 0,
                'error_probability': 0.0,
                'error_time': 0,
            }
        },
    },
}

class SequentialProcessLine(Line):
    def build(self):
        source = Source(
            name='Source',
            processing_time=10,
            unlimited_carriers=True,
            carrier_capacity=2,
            carrier_min_creation=10,
            carrier_specs=carrier_specs,
        )
        pool = WorkerPool(name='Pool', n_workers=4)

        p1 = SequentialProcess('Process1', worker_pool=pool)
        p2 = SequentialProcess('Process2', worker_pool=pool)
        sink = Sink('Sink')

        p1.connect_to_input(source, capacity=15)
        p2.connect_to_input(p1, capacity=15)
        sink.connect_to_input(p2)



class TestCarrier(unittest.TestCase):

    class EnvMock(object):

        def __init__(self):
            self.time = 0

        @property
        def now(self):
            self.time = self.time + 1
            return self.time

    def test_get_parts(self):

        carrier = Carrier(
            env=self.EnvMock(),
            name='Carrier_1',
            capacity=2,
        )

        for part_name, part_spec in carrier_specs['Type_A'].items():
            part = Part(
                env=self.EnvMock(),
                name=part_name,
                specs=part_spec,
            )
            carrier.assemble(part)

        self.assertEqual(len(carrier.get_parts_for_station('Process1')), 1)
        self.assertEqual(len(carrier.get_parts_for_station('Process2')), 2)

class TestPartDependentProcessLine(unittest.TestCase):

    def setUp(self):
        self.line = SequentialProcessLine()

    def test_get_carrier(self):
        self.line.run(simulation_end=1000, visualize=False)
        self.assertTrue(self.line.get_n_parts_produced() > 10)
