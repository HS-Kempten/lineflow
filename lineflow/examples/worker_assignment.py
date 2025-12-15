import numpy as np
from lineflow.simulation import (
    Line,
    Sink,
    Source,
    Assembly,
    Magazine,
    Switch,
    Process,
    WorkerPool,
)


def make_random_agent(n_assemblies):
    n_workers = n_assemblies * 3

    def shuffle_workers(state, env):
        """
        Shuffles every few seconds the workers
        """
        worker_names = [a.name for a in state.get_actions()["Pool"]]

        assignments = np.random.randint(n_assemblies, size=n_workers)

        return {
            'Pool': dict(zip(worker_names, assignments))
        }
    return shuffle_workers


class WorkerAssignment(Line):
    '''
    Assembly line with two assembly stations served by a component source
    '''
    def __init__(self, n_assemblies=8, n_carriers=20, with_rework=False, *args, **kwargs):
        self.with_rework = with_rework
        self.n_carriers = n_carriers
        self.n_assemblies = n_assemblies

        super().__init__(*args, **kwargs)

    def build(self):

        magazine = Magazine(
            'Setup',
            unlimited_carriers=False,
            carriers_in_magazine=self.n_carriers,
            position=(50, 100),
            carrier_capacity=self.n_assemblies,
            actionable_magazine=False,
        )

        pool = WorkerPool(name='Pool', n_workers=3*self.n_assemblies)

        sink = Sink(
            'EOL',
            position=(self.n_assemblies*100-50, 100),
            processing_time=4
        )

        sink.connect_to_output(magazine, capacity=6)

        # Create assemblies
        assemblies = []
        for i in range(self.n_assemblies):
            a = Assembly(
                f'A{i}',
                position=((i+1)*100-50, 300),
                processing_time=16+4*i,
                worker_pool=pool,
            )

            s = Source(
                f'SA{i}',
                position=((i+1)*100-50, 450),
                processing_time=2,
                unlimited_carriers=True,
                carrier_capacity=1,
                actionable_waiting_time=False,
            )

            a.connect_to_component_input(s, capacity=2, transition_time=4)
            assemblies.append(a)
        # connect assemblies
        magazine.connect_to_output(assemblies[0], capacity=4, transition_time=10)
        for a_prior, a_after in zip(assemblies[:-1], assemblies[1:]):
            a_prior.connect_to_output(a_after, capacity=2, transition_time=10)

        if self.with_rework:

            rework_switch = Switch("ReworkStart", alternate=True, position=(750, 300))
            rework_switch.connect_to_input(assemblies[-1], capacity=2, transition_time=10)

            distribute_switch = Switch("Distribute", alternate=True, position=(900, 400))
            distribute_switch.connect_to_input(rework_switch)

            collect_switch = Switch("Collect", alternate=True, position=(900, 100))

            for i in range(3):
                p = Process(f'R{i+1}', position=(850+i*50, 250))
                p.connect_to_input(distribute_switch, capacity=2, transition_time=2)
                p.connect_to_output(collect_switch, capacity=2, transition_time=2)

            rework_end_switch = Switch("ReworkEnd", alternate=True, position=(750, 200))
            rework_end_switch.connect_to_input(rework_switch, capacity=2, transition_time=2)
            rework_end_switch.connect_to_input(collect_switch, capacity=2, transition_time=2)
            rework_end_switch.connect_to_output(sink, capacity=2, transition_time=2)
        else:
            assemblies[-1].connect_to_output(sink, capacity=4)


if __name__ == '__main__':
    line = WorkerAssignment(with_rework=True, realtime=False, n_assemblies=7, step_size=2)

    agent = make_random_agent(7)
    line.run(simulation_end=1000, agent=agent, visualize=True, capture_screen=False)
