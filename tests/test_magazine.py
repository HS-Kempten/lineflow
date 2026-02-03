import unittest
import numpy as np
import simpy
from lineflow.simulation import (
    Buffer,
    Source,
    Sink,
    Line,
    Process,
    Magazine,
)


class SimplestLine(Line):

    def build(self):

        m = Magazine(
            'Magazine',
            carriers_in_magazine=10,
            unlimited_carriers=False,
            position=(200, 300),
        )

        source = Source(
            'Source',
            processing_time=2,
            position=(400, 300),
        )

        m.connect_to_output(
            station=source,
            capacity=5,
            transition_time=5,
        )

        source.connect_to_output(
            station=Sink(
                'Sink',
                processing_time=1,
                position=(600, 300),
            ),
            capacity=5,
            transition_time=5,
        )


class LineWithReturn(Line):

    def build(self):

        # Configure a simple line
        buffer_1 = Buffer('Buffer1', capacity=5, transition_time=5)
        buffer_2 = Buffer('Buffer2', capacity=5, transition_time=5)
        buffer_3 = Buffer('Buffer3', capacity=5, transition_time=5)
        buffer_4 = Buffer('Buffer4', capacity=5, transition_time=5)

        Magazine(
            'Magazine',
            unlimited_carriers=False,
            carriers_in_magazine=20,
            position=(100, 300),
            buffer_out=buffer_3,
            buffer_in=buffer_4,
        )

        Source(
            'Source',
            processing_time=2,
            buffer_out=buffer_1,
            buffer_in=buffer_3,
            position=(100, 300),

        )

        Process(
            'process',
            buffer_in=buffer_1,
            buffer_out=buffer_2,
            processing_time=2,
            position=(300, 100)
        )

        Sink(
            'Sink',
            buffer_in=buffer_2,
            buffer_out=buffer_4,
            processing_time=1,
            position=(600, 300),
        )


class TestMagazine(unittest.TestCase):

    def setUp(self):
        self.line = LineWithReturn()
        self.line.build()

        self.simplest_line = SimplestLine()
        self.simplest_line.build()

    def test_wrong_set_up(self):
        '''
        Some Magazine set ups do not make sense.
        '''

        with self.assertRaises(AttributeError):
            buffer_1 = Buffer('Buffer1', capacity=5, transition_time=5)
            buffer_2 = Buffer('Buffer2', capacity=5, transition_time=5)
            # Magazine with both buffer in and create unlimited carriers
            Magazine(
                'Magazine',
                buffer_out=buffer_1,
                buffer_in=buffer_2,
                unlimited_carriers=True,
                position=(100, 300),
            )

        with self.assertRaises(AttributeError):
            # Magazine without create unlimited carriers and empty magazine
            buffer_1 = Buffer('Buffer1', capacity=5, transition_time=5)
            buffer_2 = Buffer('Buffer2', capacity=5, transition_time=5)

            Magazine(
                'Magazine',
                buffer_out=buffer_2,
                buffer_in=buffer_1,
                carriers_in_magazine=0,
                position=(100, 300),
                unlimited_carriers=False,
            )

    def test_magazine_setup(self):
        self.assertEqual(
            self.line.state["Magazine"]["carriers_in_magazine"].value,
            20,
        )

    def test_magazine_removal(self):
        self.simplest_line.run(simulation_end=50)

        df = self.simplest_line.get_observations('Magazine')

        self.assertTrue(
            np.all(df['carriers_in_magazine'][:-1].values >= df['carriers_in_magazine'][1:].values)
        )

    def test_magazine_fill(self):
        self.line.run(simulation_end=50)

        df = self.line.get_observations('Magazine')
        np.testing.assert_array_less(0, df['carriers_in_magazine'])

    def test_carrier_removal_by_policy(self):

        self.removal_line = SimplestLine()
        self.removal_line.build()

        def policy(line_state, env):
            '''
            policy that stops Magazine from timestep 2 on
            '''
            actions = {}

            if env.now >= 7:
                actions['Magazine'] = {'carriers_in_magazine': 0}

            return actions

        self.removal_line.run(simulation_end=50, agent=policy)
        df = self.removal_line.get_observations("Magazine")
        # Magazine produces carrier 'Magazine_cr_2'
        self.assertTrue(df.iloc[5].carrier, 'Magazine_cr_2')
        # Afterwards no more carriers
        self.assertListEqual(df.iloc[6:].carrier.unique().tolist(), [np.nan])

    def test_carrier_inseration_by_policy(self):

        self.removal_line = SimplestLine()
        self.removal_line.build()

        def policy(line_state, env):
            '''
            policy that stops Magazine from timestep 2 on
            '''
            actions = {}

            if env.now > 3 and env.now < 5:
                actions['Magazine'] = {'carriers_in_magazine': 0}
            if env.now >= 5:
                actions['Magazine'] = {'carriers_in_magazine': 1}

            return actions

        self.removal_line.run(simulation_end=50, agent=policy)
        df = self.removal_line.get_observations("Magazine")
        # Magazine produces carrier 'Magazine_cr_1'
        self.assertEqual(df.iloc[2].carrier, 'Magazine_carrier_1')
        # Afterwards all carriers are removed exept one (the tenth)
        self.assertEqual(df.iloc[5].carrier, 'Magazine_carrier_10')

    def test_carrier_specs(self):
        source = Source(
            name="TestSource",
            carrier_specs={
                'Carrier1': {
                    'Part1': {
                        'C1': {"assembly_condition": 11},
                        'C2': {"assembly_condition": 12},
                    },
                    'Part2': {
                        'C1': {"assembly_condition": 11},
                        'C3': {"assembly_condition": 13},
                    },
                },
                'Carrier2': {
                    'Part1': {
                        'C1': {"assembly_condition": 21},
                        'C2': {"assembly_condition": 22},
                    },
                    'Part2': {
                        'C1': {"assembly_condition": 21},
                        'C3': {"assembly_condition": 23},
                    },
                }
            }
        )
        source.init(np.random.RandomState(0))
        source.env = simpy.Environment()
        carrier = source.create_carrier()

        self.assertEqual(carrier.name, 'TestSource_Carrier1_1')

        parts = source.create_parts(carrier)
        self.assertEqual(len(parts), 2)

        self.assertDictEqual(
            parts[0].specs['C1'],
            {"assembly_condition": 11},
        )
        self.assertDictEqual(
            parts[0].specs['C2'],
            {"assembly_condition": 12},
        )


        self.assertDictEqual(
            parts[1].specs['C1'],
            {"assembly_condition": 11},
        )
        self.assertDictEqual(
            parts[1].specs['C3'],
            {"assembly_condition": 13},
        )
