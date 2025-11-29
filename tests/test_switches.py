import unittest

from lineflow.simulation import (
    Line,
    Sink,
    Source,
    Process,
    Switch,
    Magazine,
)


class LineWithTwoSinks(Line):
    def build(self):

        source = Source(
            name='Source',
            processing_time=5,
            position=(200, 300),
            unlimited_carriers=True,
            carrier_capacity=1,
            actionable_magazin=False,
            actionable_waiting_time=False,
        )

        switch = Switch(
            'Switch',
            position=(300, 300),
            alternate=False,
        )

        source.connect_to_output(switch, capacity=2, transition_time=5)

        sink_slow = Sink(
            name=f'SinkSlow',
            position=(500, 200),
            processing_time=300,
            processing_std=0,
        )
        sink_fast = Sink(
            name=f'SinkFast',
            position=(500, 400),
            processing_time=10,
            processing_std=0,
        )
        sink_slow.connect_to_input(switch, capacity=4, transition_time=5)
        sink_fast.connect_to_input(switch, capacity=4, transition_time=5)



class LineWithSwitch(Line):

    def __init__(self, alternate_s1=False, alternate_s2=True, *args, **kwargs):
        self.alternate_s1 = alternate_s1
        self.alternate_s2 = alternate_s2
        super(LineWithSwitch, self).__init__(*args, **kwargs)

    def build(self):
        m1 = Magazine('M1', unlimited_carriers=True)
        m2 = Magazine('M2', unlimited_carriers=True)

        c1 = Source('C1')
        c2 = Source('C2')

        s1 = Switch('S1', alternate=self.alternate_s1, position=(200, 200))

        p1 = Process('P1', processing_std=0)
        p2 = Process('P2', processing_std=0)
        p3 = Process('P3', processing_std=0)

        c1.connect_to_input(m1)
        c2.connect_to_input(m2)
        s1.connect_to_input(c1)
        s1.connect_to_input(c2)
        s1.connect_to_output(p1)
        s1.connect_to_output(p2)
        s1.connect_to_output(p3)

        s2 = Switch('S2', alternate=self.alternate_s2, position=(200, 400))

        s2.connect_to_input(p1)
        s2.connect_to_input(p2)
        s2.connect_to_input(p3)
        s2.connect_to_output(Sink('Sink', position=(200, 500)))


class TestSwitches(unittest.TestCase):

    def get_unique_parts(self, line, station):

        df = line.get_observations(station).carrier
        return df[df.notna()].unique().tolist()

    def get_parts_at_processes(self, line):
        p1 = self.get_unique_parts(line, 'P1')
        p2 = self.get_unique_parts(line, 'P2')
        p3 = self.get_unique_parts(line, 'P3')

        return p1, p2, p3

    def test_without_alternate(self):
        line = LineWithSwitch(alternate_s1=False, alternate_s2=False)
        line.run(100)

        # All parts should visit P1, none vists P2 and P3
        p1, p2, p3 = self.get_parts_at_processes(line)
        self.assertListEqual(p1, [f'M1_{i}' for i in range(1, 7)])
        self.assertListEqual(p2, [])
        self.assertListEqual(p3, [])

    def test_alternation_from_full_buffer(self):
        def agent(state, env):
            if env.now > 100:
                return {'Switch': {'index_buffer_out': 1}}
            else:
                return {'Switch': {'index_buffer_out': 0}}
        line = LineWithTwoSinks(realtime=False)
        line.run(simulation_end=200, agent=agent)
        df = line.state.df()

        # Fast sink does not produce any part before 100
        self.assertEqual(
            df[df["T_end"] < 100]['SinkFast_n_parts_produced'].max(),
            0,
        )

        self.assertGreater(
            df[df["T_end"] > 100]['SinkFast_n_parts_produced'].max(),
            1,
        )

    def test_alternate(self):
        line = LineWithSwitch(alternate_s1=True, alternate_s2=True)
        line.run(120)

        p1, p2, p3 = self.get_parts_at_processes(line)

        self.assertListEqual(
            p1, 
            ['M1_1', 'M2_2', 'M1_4', 'M2_5']
        )
        self.assertListEqual(
            p2, 
            ['M2_1', 'M1_3', 'M2_4', 'M1_6']
        )
        self.assertListEqual(
            p3, 
            ['M1_2', 'M2_3', 'M1_5']
        )

    def test_with_policy_on_fixed_index(self):

        def policy(*args):
            return {
                'S1': {'index_buffer_out': 1, 'index_buffer_in': 1},
                'S2': {'index_buffer_in': 1},
            }

        line = LineWithSwitch(alternate_s1=False, alternate_s2=False)

        # Initial states are set to 0, set initially to 1
        line.state['S1']['index_buffer_out'].update(1)
        line.state['S1']['index_buffer_in'].update(1)
        line.state['S2']['index_buffer_in'].update(1)

        line.run(100, agent=policy)
        p1, p2, p3 = self.get_parts_at_processes(line)
        self.assertListEqual(p1, [])
        self.assertListEqual(p2, [f'M2_{i}' for i in range(1, 7)])
        self.assertListEqual(p3, [])
