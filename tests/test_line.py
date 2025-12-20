import unittest
import numpy as np
import pygame

from lineflow.helpers import compute_processing_times_of_parts
from lineflow.simulation.stationary_objects import StationaryObject
from lineflow.examples.showcase_line import ShowCase
from lineflow.simulation import (
    Line,
    Buffer,
    Sink,
    Source,
    Assembly,
    Magazine,
    Station,
)


class LineWithAssembly(Line):

    def __init__(self, std=None, *args, **kwargs):
        self.std = std
        super().__init__(*args, **kwargs)

    def build(self):

        m1 = Magazine(
            name='M1', 
            unlimited_carriers=True, 
            carrier_specs={
                'A': {'Part': {'C2': {"assembly_condition": 20}}}
            }
        )

        m2 = Magazine('M2', unlimited_carriers=True)

        a1 = Source('A1')

        c1 = Source('C1')

        sink = Sink('Sink')

        c2 = Assembly(
            'C2',
            processing_time=5,
            processing_std=self.std,
            position=(100, 300),
        )

        a1.connect_to_input(m1, capacity=5)
        c1.connect_to_input(m2, capacity=5)
        c2.connect_to_input(c1, capacity=5)
        c2.connect_to_component_input(a1, capacity=4)
        sink.connect_to_input(c2, capacity=5)


class LineWithDuplicates(Line):

    def build(self):
        # Configure a simple line
        Buffer('A', capacity=4, transition_time=10)
        Buffer('A', capacity=5, transition_time=10)


class TestAssemblyLine(unittest.TestCase):

    def setUp(self):
        self.line = LineWithAssembly(std=0)

    def compute_processing_times_of_parts(self, line):
        return compute_processing_times_of_parts(line, 'C2', finished_only=True)

    def test_simulate(self):
        self.line.run(simulation_end=15)

    def test_element_access(self):
        self.assertIsInstance(self.line['Buffer_C1_to_C2'], Buffer)
        self.assertIsInstance(self.line['C2'], Assembly)

    def test_valid_carrier_specs(self):
        self.line.run(simulation_end=15)

        with self.assertRaises(ValueError):
            self.line._validate_carrier_specs(
                {'carrier_name': {
                    'Part': {
                        'C2': {"assembly_condition": 20},
                        'M2': {"assembly_condition": 20},
                        'C33': {"assembly_condition": 20}
                    }
                }})

    def test_processing_times_with_randomization(self):
        line = LineWithAssembly(std=0.9)

        line.run(simulation_end=100)
        processing_times = self.compute_processing_times_of_parts(line)
        self.assertTrue(
            np.all(processing_times >= 5)
        )

    def test_processing_times_without_randomization(self):
        self.line.run(simulation_end=100)
        processing_times = self.compute_processing_times_of_parts(self.line)
        np.testing.assert_array_almost_equal(processing_times, 5, decimal=9)

    def test_part_count(self):
        self.line.run(simulation_end=100)
        self.assertEqual(self.line.get_n_parts_produced(), 4)

    def test_all_objects_tracked(self):

        self.assertSetEqual(
            set(self.line._objects.keys()),
            {
                'M1', 'M2', 'C1', 'A1', 'C2', 'Sink',   # Stations
                # Buffers
                'Buffer_M1_to_A1',
                'Buffer_M2_to_C1',
                'Buffer_C1_to_C2',
                'Buffer_A1_to_C2',
                'Buffer_C2_to_Sink',
            }
        )

    def test_exception_on_duplicate_names(self):

        with self.assertRaises(ValueError):
            LineWithDuplicates()

    def test_context_tracking(self):
        with StationaryObject() as objects:
            Buffer('A')
            Buffer('B')
            Buffer('C')

        self.assertEqual(len(objects), 3)
        self.assertSetEqual(
            {o.name for o in objects},
            {'A', 'B', 'C'}
        )

        for o in objects:
            self.assertIsInstance(o, Buffer)

    def test_step_function(self):
        self.line = LineWithAssembly(std=0)
        state, terminated = self.line.step()
        # Check if step size time is passed
        self.assertTrue(state.df()["T_end"].item() == self.line.step_size)
        state, terminated = self.line.step()
        # Check if another step_size is passed
        self.assertTrue(state.df()["T_end"].iloc[-1] == self.line.step_size * 2)
