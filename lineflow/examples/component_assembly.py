from lineflow.simulation import (
    Line,
    Switch,
    Sink,
    Source,
    Process,
    Assembly,
    Magazine,
)


class ComponentAssembly(Line):
    '''
    Assembly line with two assembly stations served by a component source
    '''

    assembly_condition = 40

    def build(self):

        source_main = Source(
            'C1',
            position=(80, 300),
            processing_time=2,
        )

        # Component line
        source_component = Source(
            'A1',
            processing_time=4,
            position=(500, 300),
            carrier_specs={
                'A': {
                    'ComponentA': {
                        'C21': {"assembly_condition": 40},
                        'C22': {"assembly_condition": 40},
                    }
                }
            },
            unlimited_carriers=True,
            carrier_capacity=1,
        )

        switch1 = Switch('S1', alternate=True, position=(200, 300),)
        switch2 = Switch('S2', alternate=True, position=(300, 300))
        switch3 = Switch('S3', alternate=True, position=(580, 300))
        switch4 = Switch('S4', alternate=True, position=(780, 300))
        switch5 = Switch('S5', alternate=True, position=(780, 550),)

        assembly1 = Assembly(
            'C21',
            position=(400, 150),
            processing_time=8,
        )

        assembly2 = Assembly(
            'C22',
            position=(400, 500),
            processing_time=10,
        )

        process = Process('C3', processing_time=6, position=(700, 200))

        c41 = Process(
            'C41',
            processing_time=15,
            processing_std=0.1,
            position=(680, 400),
            rework_probability=0.1,
        )

        c42 = Process(
            'C42',
            processing_time=15,
            # This cell has higher scale
            processing_std=0.5,
            position=(780, 400),
            rework_probability=0.5,
        )

        c43 = Process(
            'C43',
            processing_time=15,
            processing_std=0.1,
            position=(880, 400),
            rework_probability=0.1,
        )

        magazine = Magazine(
            name='Magazin',
            position=(80, 550),
            unlimited_carriers=False,
            carrier_capacity=3,
            carriers_in_magazine=30,
        )

        source_other_component = Source(
            'A2',
            processing_time=5,
            position=(600, 400),
            carrier_specs={
                'B': {
                    'Component_B': {
                        'C5': {"assembly_condition": 400},
                    }
                }
            },
            unlimited_carriers=True,
            carrier_capacity=1,
        )

        assembly3 = Assembly(
            'C5',
            position=(600, 550),
            processing_time=8,
        )

        assembly3.connect_to_component_input(source_other_component, capacity=3)

        sink = Sink('C6', position=(400, 550))

        sink.connect_to_output(magazine, capacity=8)
        magazine.connect_to_output(source_main, capacity=4)

        source_main.connect_to_output(switch1, capacity=2, transition_time=10)
        switch1.connect_to_output(assembly1, capacity=4, transition_time=10)
        switch1.connect_to_output(assembly2, capacity=4, transition_time=10)

        switch3.connect_to_input(assembly1, capacity=5, transition_time=15)
        switch3.connect_to_input(assembly2, capacity=5, transition_time=15)

        process.connect_to_input(switch3, capacity=3, transition_time=6)
        process.connect_to_output(switch4, capacity=2, transition_time=6)

        switch4.connect_to_output(c41, capacity=3, transition_time=10)
        switch4.connect_to_output(c42, capacity=3, transition_time=10)
        switch4.connect_to_output(c43, capacity=3, transition_time=10)

        switch5.connect_to_input(c41, capacity=3, transition_time=10)
        switch5.connect_to_input(c42, capacity=3, transition_time=10)
        switch5.connect_to_input(c43, capacity=3, transition_time=10)
        switch5.connect_to_output(assembly3, capacity=4, transition_time=10)

        assembly3.connect_to_output(sink, capacity=3, transition_time=10)

        switch2.connect_to_input(source_component, capacity=2, transition_time=5)
        assembly1.connect_to_component_input(switch2, capacity=4, transition_time=10)
        assembly2.connect_to_component_input(switch2, capacity=4, transition_time=10)


if __name__ == '__main__':
    line = ComponentAssembly(realtime=True, factor=0.5)
    line.run(simulation_end=10_000, visualize=True)
