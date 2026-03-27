import numpy as np
from gekko import GEKKO
from lineflow.simulation import (
    Line,
    Sink,
    Source,
    Assembly,
    Magazine,
    Switch,
    WorkerPool,
)


def compute_balanced_optimum(state, n_assemblies, n_workers):
    processing_times = np.array([state[f'A{i}']['processing_time'].value for i in range(n_assemblies)])

    m = GEKKO(remote=False)

    n = m.Array(m.Var, dim=n_assemblies, value=n_workers//n_assemblies, ub=n_workers, lb=0, integer=True)

    # Intermediate variables
    times = []
    for i in range(n_assemblies):
        t = m.Intermediate(processing_times[i] * m.exp(-(n[i]) * 0.3) + processing_times[i] * 0.1)
        times.append(t)
    t_mean = m.Intermediate(1/n_assemblies * m.sum([t for t in times]))

    # Equations
    m.Equation(m.sum(n) == n_workers)
    for i in range(n_assemblies-1):
        m.Equation(n[i] <= n[i+1])

    # Objective
    m.Minimize(m.sum([(t - t_mean)**2 for t in times]))
   
    m.options.SOLVER = 1
    m.solve(debug=0, disp=False)

    m.cleanup()
    return np.array([n[i].value[0] for i in range(n_assemblies)]).astype(int)


def get_last_filled_buffer(fills_btw_assemblies):
    return (len(fills_btw_assemblies) - 
            np.argmax(np.flip(fills_btw_assemblies)))


def get_filled_buffers(fills_assembly_switch, fills_btw_assemblies):
    filled_positions = np.nonzero(fills_btw_assemblies)[0]
    if filled_positions.shape == (0,):
        filled_positions = np.array([0])
    return np.argmin(fills_assembly_switch[filled_positions])


def get_fill_factor(fills_assembly_switch, fills_btw_assemblies):
    return (0.9 * (np.sum(fills_assembly_switch) / len(fills_assembly_switch)) +
            0.1 * (np.sum(fills_btw_assemblies) / len(fills_btw_assemblies)))


def index_for_waiting_time(waiting_times, waiting_time):
    return np.argmin(np.abs(waiting_times - waiting_time))


def make_agent(
    state,
    n_assemblies,
    n_workers,
    waiting_time=0,
    ramp_up_waiting_time=0,
    get_max_reward=False
):
    # worker distribution
    workers = compute_balanced_optimum(state, n_assemblies, n_workers)

    def agent(state, env):
        actions = {}

        # worker assignment
        worker_assignment = np.concatenate(
            [np.full(workers[i], i) for i in range(n_assemblies)]
        )
        worker_names = [worker.name for worker in state.get_actions()["Pool"]]
        actions['Pool'] = dict(zip(worker_names, worker_assignment))

        # get fills of all buffers between the switch and the assemblys
        fills_assembly_switch = np.array(
            [state[f'Buffer_Switch_to_A{i}']['fill'].value for i in range(n_assemblies)]
        )
        # get fills of all buffers between the assemblys
        fills_btw_assemblies = np.array(
            [state[f'Buffer_A{i}_to_A{i+1}']['fill'].value for i in range(n_assemblies-1)]
        )

        waiting_times = state['Source']['waiting_time'].categories

        if get_max_reward:
            actions['Switch'] = {'index_buffer_out': fills_assembly_switch.argmin()}
            actions['Source'] = {'waiting_time': 0}

        else:
            # find last filled buffer between the assemblys
            if (fills_assembly_switch[get_last_filled_buffer(fills_btw_assemblies)] == 0
                and fills_btw_assemblies[get_last_filled_buffer(fills_btw_assemblies) - 1] > 0):
                actions['Switch'] = {
                    'index_buffer_out': get_last_filled_buffer(fills_btw_assemblies)
                }
                actions['Source'] = {'waiting_time': 0}
            # check buffer to the first assembly and buffer between first and second assembly
            elif fills_assembly_switch[0] == 0 and fills_btw_assemblies[0] <= 0.5:
                actions['Switch'] = {'index_buffer_out': 0}
                # ramp up
                if state['EOL']['n_parts_produced'].value == 0:
                    actions['Source'] = {
                        'waiting_time': index_for_waiting_time(
                            waiting_times, ramp_up_waiting_time
                        )
                    }
                else:
                    actions['Source'] = {'waiting_time': 0}
            else:
                # ramp up, distribute greedy, up to last filled buffer between the assemblys
                if state['EOL']['n_parts_produced'].value == 0:
                    actions['Switch'] = {
                        'index_buffer_out': get_filled_buffers(
                            fills_assembly_switch, fills_btw_assemblies
                        )
                    }
                    actions['Source'] = {
                        'waiting_time': index_for_waiting_time(
                            waiting_times, ramp_up_waiting_time
                        )
                    }
                # distribute greedy to all ass., waiting_time depends on fills of buffers
                else:
                    actions['Switch'] = {
                        'index_buffer_out': fills_assembly_switch.argmin()
                    }
                    actions['Source'] = {
                        'waiting_time': np.round(
                            get_fill_factor(
                                fills_assembly_switch, fills_btw_assemblies
                            ) * index_for_waiting_time(
                                waiting_times, waiting_time
                                )
                        ).astype(int)
                    }
        return actions

    return agent


class ComplexLine(Line):
    '''
    Assembly line with a configurable number of assembly stations served by a component source
    '''
    def __init__(
            self,
            n_workers,
            n_assemblies=8,
            n_carriers=20,
            alternate=True,
            assembly_condition=30,
            *args,
            **kwargs
    ):
        self.n_carriers = n_carriers
        self.alternate = alternate
        self.n_assemblies = n_assemblies
        self.n_workers = n_workers
        self.assembly_condition = assembly_condition

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

        pool = WorkerPool(name='Pool', n_workers=self.n_workers, transition_time=2)

        sink = Sink(
            'EOL',
            position=(self.n_assemblies*100-50, 100),
            processing_time=2
        )

        sink.connect_to_output(magazine, capacity=6, transition_time=6)

        source = Source(
            'Source',
            position=((self.n_assemblies/2)*100+200, 150),
            processing_time=1,
            unlimited_carriers=True,
            carrier_capacity=1,
            actionable_waiting_time=True,
            carrier_specs={
                'Carrier': {
                    'Part': {
                        f'A{i}': {"assembly_condition": self.assembly_condition} for i in range(self.n_assemblies)
                    }
                }
            }
        )

        switch = Switch(
            'Switch',
            position=((self.n_assemblies/2)*100, 150),
            alternate=self.alternate,
            processing_time=0,
        )

        source.connect_to_output(switch, capacity=2, transition_time=2)

        # Create assemblies
        assemblies = []
        for i in range(self.n_assemblies):
            a = Assembly(
                f'A{i}',
                position=((i+1)*100-50, 300),
                processing_time=16+4*i,
                worker_pool=pool,
                NOK_part_error_time=2,
            )

            a.connect_to_component_input(switch, capacity=4, transition_time=4)
            assemblies.append(a)
        # connect assemblies
        magazine.connect_to_output(assemblies[0], capacity=4, transition_time=4)
        for a_prior, a_after in zip(assemblies[:-1], assemblies[1:]):
            a_prior.connect_to_output(a_after, capacity=2, transition_time=10)

        assemblies[-1].connect_to_output(sink, capacity=4, transition_time=4)


if __name__ == '__main__':
    ramp_up_waiting_time = 10
    waiting_time = 5
    n_assemblies = 5
    n_workers = 3*n_assemblies
    scrap_factor = 1/n_assemblies

    line = ComplexLine(
        realtime=False,
        factor=0.05,
        alternate=False,
        n_assemblies=n_assemblies,
        n_workers=n_workers,
        step_size=1,
        scrap_factor=scrap_factor,
        random_state=0,
        assembly_condition=30
    )

    agent = make_agent(
        state=line.state,
        ramp_up_waiting_time=ramp_up_waiting_time,
        waiting_time=waiting_time,
        n_assemblies=n_assemblies,
        n_workers=n_workers,
        get_max_reward=False
        )

    line.run(simulation_end=4000, agent=agent, show_status=True, visualize=False)
    print("Produced: ", line.get_n_parts_produced())
    print("Scrap: ", line.get_n_scrap_parts())
    print("Reward: ",  line.get_n_parts_produced() - line.get_n_scrap_parts()*scrap_factor)
