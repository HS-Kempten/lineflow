from lineflow.simulation import (
    Buffer,
    Source,
    Sink,
    Line,
    Process,
)

class SimpleLine(Line):

    def build(self):

        # Configure a simple line
        buffer_2 = Buffer('Buffer2', capacity=5, transition_time=5)
        buffer_3 = Buffer('Buffer3', capacity=3,  transition_time=3)

        Source(
            name='Source',
            processing_time=5,
            buffer_out=buffer_2,
            position=(100, 500),
            waiting_time=10,
            unlimited_carriers=True,
            carrier_capacity=1,
        )

        Process(
            'Process',
            buffer_in=buffer_2,
            buffer_out=buffer_3,
            position=(350, 500),
        )

        Sink(
            'Sink',
            buffer_in=buffer_3,
            position=(600, 500),
        )


if __name__ == '__main__':
    line = SimpleLine()
    line.run(simulation_end=3_000, visualize=True)
