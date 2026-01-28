import numpy as np
from lineflow.simulation import (
    Line,
    Sink,
    Source,
    Switch,
    Process,
)


def make_fast_only_policy(n_processes):
    def policy(state, env):
        return {
            'SwitchF': {'index_buffer_in': 0, 'index_buffer_out': 0},
            'SwitchD': {'index_buffer_in': 0, 'index_buffer_out': 0},
        }
    return policy


def make_greedy_policy(n_processes):
    def policy(state, env):
        # Fetch from buffer where fill is largest
        fills_prior_process = np.array(
            [state[f'Buffer_SwitchD_to_P{i}']['fill'].value for i in range(n_processes)]
        )
        fills_after_process = np.array(
            [state[f'Buffer_P{i}_to_SwitchF']['fill'].value for i in range(n_processes)]
        )
        return {
            # Fetch where fill is maximal
            'SwitchF': {
                'index_buffer_in': fills_after_process.argmax(),
                },
            # Push where fill is minimal
            'SwitchD': {
                'index_buffer_out': fills_prior_process.argmin()
            },
        }
    return policy


class MultiProcess(Line):
    """
    Assembly line with two sources a switch and a sink
    """

    def __init__(self, alternate=True, n_processes=5, **kwargs):
        self.alternate = alternate
        self.n_processes = n_processes
        super().__init__(**kwargs)

    def build(self):
        source = Source(
            name='Source',
            processing_time=2,
            actionable_magazin=False,
            actionable_waiting_time=False,
            unlimited_carriers=True,
            carrier_capacity=1,
            position=(50, 300),
            processing_std=0,
        )

        switch_d = Switch(
            'SwitchD',
            position=(200, 300),
            alternate=self.alternate,
            processing_time=1,
        )

        switch_f = Switch(
            'SwitchF',
            position=(900, 300),
            alternate=self.alternate,
            processing_time=1,
        )

        processes = []
        for i in range(self.n_processes):
            processes.append(
                Process(
                    name=f'P{i}',
                    processing_time=12+10*i,
                    position=(600, 500-100*i),
                    processing_std=0.1,
                )
            )
        sink = Sink('Sink', position=(1100, 300), processing_time=1, processing_std=0)
        switch_f.connect_to_output(sink, capacity=2, transition_time=5)
        switch_d.connect_to_input(source, capacity=2, transition_time=5)

        for process in processes:
            process.connect_to_input(switch_d, capacity=8, transition_time=7)
            process.connect_to_output(switch_f, capacity=5, transition_time=7)


if __name__ == "__main__":
    n_processes = 10
    line = MultiProcess(n_processes=n_processes, realtime=True, factor=0.1, alternate=False)
    agent = make_greedy_policy(n_processes)
    line.run(simulation_end=3000, agent=agent, visualize=True)

    print('Number of parts produced: ', line.get_n_parts_produced())
