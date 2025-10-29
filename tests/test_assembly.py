import unittest
from lineflow.simulation import (
    Buffer,
    Assembly,
    Source,
    Sink,
    Line,
    Magazine,
)


class SimpleLine(Line):

    def build(self):

        # Configure a simple line
        buffer_2 = Buffer('Buffer2', capacity=5, transition_time=5, put_std=0)
        buffer_3 = Buffer('Buffer3', capacity=5, transition_time=5, put_std=0)
        buffer_4 = Buffer('Buffer4', capacity=5, transition_time=5, put_std=0)

        Source(
            'Source',
            processing_time=2,
            processing_std=0,
            buffer_out=buffer_2,
            unlimited_carriers=True,
            carrier_capacity=2,
            position=(100, 100),
        )

        Source(
            'Component Source',
            processing_time=2,
            processing_std=0,
            buffer_out=buffer_3,
            position=(300, 400),
            carrier_specs={
                'A': {'Part': {'Assembly': {"assembly_condition": 10}}}
            },
            unlimited_carriers=True,
            carrier_capacity=1,
        )

        Assembly(
            'Assembly',
            buffer_in=buffer_2,
            buffer_out=buffer_4,
            buffer_component=buffer_3,
            position=(300, 200),
        )

        Sink(
            'Sink',
            buffer_in=buffer_4,
            processing_time=1,
            processing_std=0,
            position=(600, 200),
        )


class SimpleLineWithValidProcessingCondition(Line):

    def build(self):

        # Configure a simple line
        buffer_1 = Buffer('Buffer1', capacity=5, transition_time=5, put_std=0)
        buffer_2 = Buffer('Buffer2', capacity=5, transition_time=5, put_std=0)
        buffer_3 = Buffer('Buffer3', capacity=5, transition_time=5, put_std=0)
        buffer_4 = Buffer('Buffer4', capacity=5, transition_time=5, put_std=0)
        buffer_5 = Buffer('Buffer5', capacity=5, transition_time=5, put_std=0)

        Magazine(
            'Magazine Source',
            buffer_out=buffer_1,
            carrier_capacity=2,
            position=(100, 100),
        )

        Magazine(
            'Magazine Component Source',
            buffer_out=buffer_5,
            carrier_capacity=1,
            position=(500, 500),
        )

        Source(
            'Source',
            processing_time=2,
            processing_std=0,
            buffer_in=buffer_1,
            buffer_out=buffer_2,
            position=(300, 100),
        )

        Source(
            'Component Source',
            processing_time=2,
            processing_std=0,
            buffer_in=buffer_5,
            buffer_out=buffer_3,
            position=(300, 400),
            carrier_specs={
                'A': {'Part': {'Assembly': {"assembly_condition": 14}}}
            },
        )

        Assembly(
            'Assembly',
            buffer_in=buffer_2,
            buffer_out=buffer_4,
            buffer_component=buffer_3,
            position=(500, 100),
            processing_std=0,
        )

        Sink(
            'Sink',
            buffer_in=buffer_4,
            processing_time=1,
            processing_std=0,
            position=(700, 100),
        )



class SimpleLineWithSendingBack(Line):

    def build(self):

        # Configure a simple line
        buffer_1 = Buffer('Buffer1', capacity=5, transition_time=5, put_std=0)
        buffer_2 = Buffer('Buffer2', capacity=5, transition_time=5, put_std=0)
        buffer_3 = Buffer('Buffer3', capacity=5, transition_time=5, put_std=0)
        buffer_4 = Buffer('Buffer4', capacity=5, transition_time=5, put_std=0)
        buffer_5 = Buffer('Buffer5', capacity=5, transition_time=5, put_std=0)
        buffer_6 = Buffer('Buffer6', capacity=5, transition_time=5, put_std=0)

        Magazine(
            'Magazine Source',
            buffer_out=buffer_1,
            carriers_in_magazine=1,
            unlimited_carriers=False,
        )
        Magazine(
            'Magazine Component Source',
            buffer_out=buffer_6,
            carriers_in_magazine=1,
            unlimited_carriers=False,
        )

        Source(
            'Source',
            processing_time=2,
            processing_std=0,
            buffer_in=buffer_1,
            buffer_out=buffer_2,
            position=(100, 200),
        )

        Source(
            'Component Source',
            processing_time=2,
            processing_std=0,
            buffer_out=buffer_3,
            buffer_in=buffer_5,
            position=(300, 400),
            carrier_specs={
                'A': {'Part': {'Assembly': {"assembly_condition": 5}}}
            },
        )

        Assembly(
            'Assembly',
            buffer_in=buffer_2,
            buffer_out=buffer_4,
            buffer_component=buffer_3,
            buffer_return=buffer_5,
            position=(300, 200),
            processing_std=0,
        )

        Sink(
            'Sink',
            buffer_in=buffer_4,
            processing_time=1,
            processing_std=0,
            position=(600, 200),
        )


class TestAssembly(unittest.TestCase):

    def setUp(self):
        self.line = SimpleLine(realtime=False)
        self.line.build()
        self.line.run(simulation_end=50)

        self.df = self.line.get_observations('Assembly')

        self.valid_line = SimpleLineWithValidProcessingCondition()
        self.valid_line.build()
        self.valid_line.run(simulation_end=50)
        self.df_valid = self.valid_line.get_observations('Assembly')

        self.back_line = SimpleLineWithSendingBack()
        self.back_line.build()
        self.back_line.run(simulation_end=75)
        self.df_back = self.back_line.get_observations('Assembly')

    def test_transition_time(self):
        # processing(2) + 1 (put) + 5 (transition) + 1 (get)

        self.assertEqual(
            self.df[
                (self.df['carrier'].shift() != self.df['carrier']) &
                (~self.df['carrier'].isnull())
            ].iloc[0]["T_end"],
            9,
        )

        # 2 (get carrier) + 1 (put) + 5 (transition) + 1 (get) + 2 (creation) +
        # 1 (put) + 5 (transition)+ 1 (get carrier) + 1 (get carrier component)
        # 5 (processing) + 1 (put) + 1 (get next one)
        self.assertEqual(
            self.df_valid[
                (self.df_valid['carrier'] == 'Magazine Source_carrier_2') &
                (self.df_valid['carrier_component'] == 'Magazine Component Source_carrier_2')
            ].iloc[0]["T_start"],
            26
        )

    def test_assembly_condition(self):
        # Should only have one carrier + None
        self.assertEqual(len(self.df["carrier"].unique()), 2)
        

        # Should have multiple carrier_components
        self.assertGreater(len(self.df["carrier_component"].unique()), 2)


class TestMultilpleComponentBuffers(unittest.TestCase):

    class AssemblyWithMultipleComponentBuffers(Line):
    
        def build(self):
    
            source_main = Source(
                'Source',
                processing_time=2,
                processing_std=0,
                unlimited_carriers=True,
                carrier_capacity=1+3,
                position=(100, 200),
            )
    
            assembly = Assembly(
                'A',
                position=(300, 200),
            )
    
    
            sc_1 = Source('SC1',
                unlimited_carriers=True,
                position=(220, 400),
                processing_time=7,
                nok_probabability=0.2,
                carrier_specs={
                    'T1': {'Part1': {'A': {"assembly_condition": 5}}},
                    'T2': {'Part1': {'A': {"assembly_condition": 10}}}
                },
            ) 
    
            sc_2 = Source('SC2',
                unlimited_carriers=True,
                position=(300, 400),
                processing_time=2,
                nok_probabability=0.1,
                carrier_specs={
                    'T1': {'Part2': {'A': {"assembly_condition": 8}}},
                    'T2': {'Part2': {'A': {"assembly_condition": 12}}}
                },
            ) 
    
            sc_3 = Source('SC3',
                position=(380, 400),
                processing_time=5,
                unlimited_carriers=True,
                carrier_specs={
                    'T1': {'Part3': {'A': {"assembly_condition": 5}}},
                },
            ) 
    
            assembly.connect_to_component_input(sc_1, capacity=4)
            assembly.connect_to_component_input(sc_2, capacity=4)
            assembly.connect_to_component_input(sc_3, capacity=4)
    
            sink = Sink(
                'Sink',
                processing_time=1,
                processing_std=0,
                position=(600, 200),
            )
            assembly.connect_to_input(source_main)
            assembly.connect_to_output(sink)
    
    def test_run(self):
        line = TestMultilpleComponentBuffers.AssemblyWithMultipleComponentBuffers()
        line.run(200, visualize=False)
