from lineflow.simulation import (
    Source,
    Sink,
    Line,
    Process,
    SequentialProcess,
)


class PartDependentProcessLine(Line):
    """
    Example implementation of a line with part-dependent processing times. The source creates
    carriers of two types (Type_A and Type_B), each containing two parts (Part1 and Part2). The
    processing times for each process depend on the type of carrier and the parts it contains. The
    line consists of three processes (P1, P2, P3) and a sink. The processing times for each process
    are defined in the carrier_specs of the source, where extra processing time is added based on
    the type of carrier and the parts it contains.
    """
    def build(self):
        source = Source(
            name='Source',
            processing_time=10,
            position=(100, 200),
            unlimited_carriers=True,
            carrier_capacity=2,
            carrier_min_creation=10,
            carrier_specs={
                'Type_A': {
                    'Part1': {
                        'P1': {'extra_processing_time': 20}, 
                        'P2': {'extra_processing_time': 0},
                        'P3': {'extra_processing_time': 0},
                    },
                    'Part2': {
                        'P1': {'extra_processing_time': 20}, 
                        'P2': {'extra_processing_time': 0},
                        'P3': {'extra_processing_time': 0},
                    }
                },
                'Type_B': {
                    'Part1': {
                        'P1': {'extra_processing_time': 5}, 
                        'P2': {'extra_processing_time': 20},
                        'P3': {'extra_processing_time': 0},
                    },
                    'Part2': {
                        'P1': {'extra_processing_time': 5}, 
                        'P2': {'extra_processing_time': 20},
                        'P3': {'extra_processing_time': 0},
                    }
                },
            },
        )

        p1 = Process('P1', processing_time=10, position=(350, 200))
        p2 = Process('P2', processing_time=10, position=(600, 200))
        p3 = SequentialProcess('P3', processing_time=5, position=(850, 200))
        sink = Sink('Sink', position=(950, 200))

        p1.connect_to_input(source, capacity=10)
        p2.connect_to_input(p1, capacity=10)
        p3.connect_to_input(p2, capacity=10)
        sink.connect_to_input(p3)


if __name__ == '__main__':
    line = PartDependentProcessLine(realtime=True, factor=0.8)
    line.run(simulation_end=1000, visualize=True)
