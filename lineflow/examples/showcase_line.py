import numpy as np
from lineflow.simulation import (
    Source,
    Sink,
    Line,
    Assembly,
    Process,
    Switch,
)


def make_agent(waiting_time, line):
    waiting_times = line['S_component'].state['waiting_time'].categories
    index = np.argmin(np.abs(waiting_times - waiting_time))

    def agent(state, env):
        """
        A policy that can effectively set float waiting times by
        alternating between ints
        """

        actions = {}
        actions['S_component'] = {'waiting_time': index}
        return actions
    return agent


class ShowCase(Line):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def build(self):

        x = 300
        y = 150

        source_main = Source(
            'Source1',
            position=(0.8*x, y),
            processing_time=5,
            carrier_capacity=3,
            actionable_waiting_time=True,
            unlimited_carriers=True,
        )

        source_comp = Source(
            'Source2',
            position=(x*1.5, y*1.8),
            processing_time=5,
            waiting_time=0,
            carrier_capacity=1,
            carrier_specs={'Carrier': {'Part': {'Assembly': {"assembly_condition": 100}}}},
            unlimited_carriers=True,
            actionable_waiting_time=True,
        )

        assembly = Assembly(
            'Assembly',
            position=(x*1.5, y),
            processing_time=40,
            NOK_part_error_time=5,
        )

        process = Process(
            'Process',
            position=(x*1.9, y),
            processing_time=15,
        )

        switch = Switch(
            'Switch',
            position=(x*2.3, y),
            processing_time=1,
            alternate=True,
        )

        sink_1 = Sink('Sink1', processing_time=70, position=(x*2.8, y*0.5))
        sink_2 = Sink('Sink2', processing_time=70, position=(x*2.8, y*1.5))

        assembly.connect_to_component_input(station=source_comp, capacity=2, transition_time=5)
        assembly.connect_to_input(source_main, capacity=3, transition_time=5)
        process.connect_to_input(assembly, capacity=2, transition_time=2)
        switch.connect_to_input(process, capacity=2, transition_time=2)
        sink_1.connect_to_input(switch, capacity=3, transition_time=2)
        sink_2.connect_to_input(switch, capacity=3, transition_time=2)


if __name__ == '__main__':
    line = ShowCase(realtime=True, factor=0.1)
    line.run(simulation_end=150, visualize=True)
