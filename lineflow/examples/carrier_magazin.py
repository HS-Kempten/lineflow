from lineflow.simulation import (
    Buffer,
    Source,
    Sink,
    Line,
    Process,
    Magazine,
)


class SimplestLineWithReturnForPartCarriers(Line):

    def build(self):

        # Configure a simple line
        buffer_1 = Buffer('Buffer1', capacity=5, transition_time=5)
        buffer_2 = Buffer('Buffer2', capacity=5, transition_time=5)
        buffer_3 = Buffer('Buffer3', capacity=5, transition_time=5)
        buffer_4 = Buffer('Buffer4', capacity=5, transition_time=5)

        Magazine(
            'Magazine',
            carrier_capacity=1,
            carriers_in_magazine=10,
            unlimited_carriers=False,
            buffer_in=buffer_3,
            buffer_out=buffer_4,
            position=(400, 400),
        )

        Source(
            'Source',
            buffer_out=buffer_1,
            buffer_in=buffer_4,
            position=(100, 300),
            
        )

        Process(
            'Process',
            buffer_in=buffer_1,
            buffer_out=buffer_2,
            processing_time=2,
            position=(300, 100)
        )

        Sink(
            'Sink',
            buffer_in=buffer_2,
            buffer_out=buffer_3,
            position=(600, 300)
        )


if __name__ == '__main__':
    line = SimplestLineWithReturnForPartCarriers()
    line.run(simulation_end=200, visualize=True)
