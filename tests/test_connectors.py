import unittest
import numpy as np
from itertools import product
from lineflow.simulation import (
    Source,
    Sink,
    Line,
    Magazine,
)


class ShortConnector(Line):

    def __init__(self, time_source=1, time_sink=1, time_buffer=2):
        self.time_source = time_source
        self.time_sink = time_sink
        self.time_buffer = time_buffer
        super().__init__(realtime=False)

    def build(self):
        source = Source(
            name='Source',
            processing_time=self.time_source,
            processing_std=0,
            unlimited_carriers=True,
            carrier_capacity=1,
            position=(100,100),
        )

        sink = Sink(
            'Sink',
            processing_time=self.time_sink,
            # Turn randomization off
            processing_std=0,
            position=(100,200),
        )

        source.connect_to_output(
            station=sink,
            capacity=2,
            transition_time=self.time_buffer,
            put_std=0,
        )


class SimpleLine(Line):

    def __init__(self, removal_time=1, realtime=False):
        self.removal_time = removal_time
        super().__init__(realtime=realtime)

    def build(self):
        m = Magazine(
            'Magazine',
            position=(300, 300),
            carrier_getting_time=1,
            unlimited_carriers=True,
        )

        source = Source(
            name='Source',
            processing_time=1,
            # Turn randomization off
            processing_std=0,
            position=(300, 100),
        )
        sink = Sink(
            'Sink',
            processing_time=self.removal_time,
            # Turn randomization off
            processing_std=0,
            position=(500, 100)
        )

        source.connect_to_input(
            station=m,
            capacity=4,
            transition_time=15,
            put_std=0,
        )

        sink.connect_to_input(
            station=source,
            capacity=4,
            transition_time=15,
            put_std=0,
        )


class TestBuffer(unittest.TestCase):

    def test_with_fast_removal(self):
        line = SimpleLine(removal_time=1)

        line.run(60)
        df = line.get_observations('Sink')

        index = df[df['carrier'] == 'Magazine_1'].index
        t_end = df.loc[index[0] + 1, 'T_end']
        # First part should be removed after
        # 1 (getting time) + 1 (put) + 15 (transition)+ 1 (put) + 1 (process) + 1 (put) +  15 (transition) + 1 (get) + 1 (remove)

        self.assertEqual(
            t_end,
            1 + 1 + 15 + 1 + 1 + 1 + 15 + 1 + 1)

        index = df[df['carrier'] == 'Magazine_2'].index
        t_end = df.loc[index[0] + 1, 'T_end']
        # Second part should be removed after
        # 37 (time first carrier needs with removal) + 15 / 3 (time second
        #element needs for last segment in buffer)
        self.assertEqual(
            t_end,
            37 + 15/3)

        self.assertEqual(line.get_n_parts_produced(), 5)

    def test_with_slow_removal(self):
        line = SimpleLine(removal_time=100)
        line.run(40)
        df = line.get_observations('Magazine')

        # Only six parts can be created, one in sink, 4 on buffer, one in source
        self.assertEqual(df['part'].nunique(), 0)
        self.assertEqual(line.get_n_parts_produced(), 0)

    def test_simulation_resume(self):
        line = ShortConnector(
            time_source=4,
            time_sink=4,
            time_buffer=2,
        )
        line.run(100)
        # Resume
        line.run(200)
