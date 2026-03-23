import numpy as np
from lineflow.simulation import (
    Line,
    Sink,
    Source,
    Switch,
)


def make_greedy_policy(n_sink):
    def policy(state, env):
        # Fetch from buffer where fill is largest
        fills = np.array(
            [state[f'Buffer_Switch_to_Sink_{i}']['fill'].value for i in range(n_sink)]
        )
        return {'Switch': {'index_buffer_out': fills.argmin()}}
    return policy


class MultiSink(Line):
    """
    Assembly line with two sources a switch and a sink
    """

    def __init__(self, alternate=True, n_sinks=5, **kwargs):
        self.alternate = alternate
        self.n_sinks = n_sinks
        super().__init__(**kwargs)

    def build(self):

        source = Source(
            name='Source',
            processing_time=5,
            position=(100, 300),
            processing_std=0,
            unlimited_carriers=True,
            carrier_capacity=1,
            actionable_magazin=False,
            actionable_waiting_time=False,
        )

        switch = Switch(
            'Switch',
            position=(300, 300),
            alternate=self.alternate,
            processing_time=0,
        )

        source.connect_to_output(switch, capacity=2, transition_time=5)

        for i in range(self.n_sinks):
            sink = Sink(
                name=f'Sink_{i}',
                position=(500, 500-100*i),
                processing_time=10+10*i*3,
                processing_std=0,
            )
            sink.connect_to_input(switch, capacity=4, transition_time=5)


if __name__ == '__main__':
    line = MultiSink(realtime=False, n_sinks=5, alternate=False)
    agent = make_greedy_policy(5)
    line.run(simulation_end=200, agent=agent, visualize=True, capture_screen=False)
    print('Produced parts: ', line.get_n_parts_produced())
