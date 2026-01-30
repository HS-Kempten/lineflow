import unittest
import numpy as np
import pandas as pd

from lineflow.simulation.states import (
    DiscreteState,
    NumericState,
    ObjectStates,
    TokenState,
    LineStates,
)

from lineflow.examples import MultiProcess

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
        buffer_2 = Buffer('Buffer2')
        buffer_3 = Buffer('Buffer3')

        Source(
            name='Source',
            processing_time=5,
            buffer_out=buffer_2,
            waiting_time=10,
            unlimited_carriers=True,
            carrier_capacity=1,
            processing_std=0,
        )

        Process(
            'Process',
            buffer_in=buffer_2,
            buffer_out=buffer_3,
            processing_time=5,
            processing_std=0,
        )

        Sink(
            'Sink',
            buffer_in=buffer_3,
            processing_time=5,
            processing_std=0,
        )


class TestDiscreteStates(unittest.TestCase):

    def test_usage(self):

        mode = DiscreteState('mode', categories=['waiting', 'working', 'error'])

        mode.update('working')
        self.assertEqual(mode.value, 1)
        self.assertEqual(mode.to_str(), 'working')

    def test_assert_on_none_value_access(self):
        mode = DiscreteState('mode', categories=['A', 'B'])
        with self.assertRaises(AssertionError):
            mode.apply(0)

    def test_exception_on_missing_value(self):
        mode = DiscreteState('mode', categories=['waiting', 'working', 'error'], exception_on_nan=True)

        with self.assertRaises(ValueError):
            mode.value


class TestNumericalState(unittest.TestCase):

    def test_usage(self):

        state = NumericState('waiting_time', vmin=0, is_actionable=True)
        state.update(10)
        self.assertEqual(state.value, 10)

    def test_exception_on_update_invalid_state(self):
        state = NumericState('waiting_time', vmin=0, vmax=1)

        with self.assertRaises(AssertionError):
            state.update(-1)

        with self.assertRaises(AssertionError):
            state.update(2)

    def test_exception_on_apply_invalid_state(self):
        state = NumericState('waiting_time', vmin=0, vmax=1, is_actionable=True)

        with self.assertRaises(AssertionError):
            state.apply(-1)

        with self.assertRaises(AssertionError):
            state.apply(2)


class TestTokenState(unittest.TestCase):

    def test_usage(self):

        state = TokenState('carrier_name', is_actionable=True)

        state.update('carrier_1')
        self.assertEqual(state.value, 0)

        state.update('carrier_1')
        self.assertEqual(state.value, 0)

        state.update('carrier_2')
        self.assertEqual(state.value, 1)

        state.update('carrier_3')
        self.assertEqual(state.value, 2)

        state.update('carrier_abcdef')
        self.assertEqual(state.value, 3)


class TestObjectStates(unittest.TestCase):

    def setUp(self):
        self.states = ObjectStates(
            DiscreteState('mode', categories=['waiting', 'working', 'error']),
            DiscreteState('on', categories=[True, False]),
            DiscreteState('index_out', categories=[0, 1, 2, 3]),
        )

        self.states['mode'].update('waiting')
        self.states['on'].update(True)
        self.states['index_out'].update(True)

    def test_states(self):
        np.testing.assert_array_equal(
            self.states.values,
            [0, 0, 1]
        )

    def test_update(self):

        self.states.update(
            {
                'mode': 'working',
                'on': False,
                'index_out': 3
            }
        )
        self.assertDictEqual(
            self.states.to_dict(),
            {
                'mode': 1,
                'on': 1,
                'index_out': 3
            }
        )

    def test_to_dict(self):
        self.assertDictEqual(
            self.states.to_dict(),
            {
                'mode': 0,
                'on': 0,
                'index_out': 1
            }
        )

    def test_carrier_tracking(self):

        mapping = {}

        station_a = ObjectStates(
            DiscreteState('mode', categories=['waiting', 'working', 'error']),
            TokenState('carrier', is_actionable=False, mapping=mapping)
        )
        station_b = ObjectStates(
            DiscreteState('mode', categories=['waiting', 'working', 'error']),
            TokenState('carrier', is_actionable=False, mapping=mapping)
        )
        station_a['carrier'].update('carrier_2')
        station_b['carrier'].update('carrier_1')

        self.assertEqual(station_a['carrier'].value, 0)
        self.assertEqual(station_b['carrier'].value, 1)

        station_b['carrier'].update('carrier_2')
        self.assertEqual(station_b['carrier'].value, 0)


class TestLineState(unittest.TestCase):

    def setUp(self):

        station_a = ObjectStates(
            DiscreteState('mode', categories=['waiting', 'working', 'error']),
            DiscreteState('on', categories=[True, False], is_actionable=True),
            DiscreteState('index_out', categories=[0, 1, 2, 3], is_actionable=True),
        )
        station_a.update(
            {
                'mode': 'error',
                'on': True,
                'index_out': 2
            }
        )

        station_b = ObjectStates(
            DiscreteState('mode', categories=['waiting', 'working', 'error']),
            DiscreteState('on', categories=[True, False], is_actionable=True),
            TokenState('carrier', is_actionable=False, is_observable=False)
        )
        station_b.update(
            {
                'mode': 'waiting',
                'on': True,
                'carrier': None,
            }
        )

        class EnvMock(object):

            def __init__(self):
                self.time = 0

            @property
            def now(self):
                self.time = self.time + 1
                return self.time

        self.line_state = LineStates(
            objects={
                'station_a': station_a,
                'station_b': station_b,
            },
            env=EnvMock()
        )

    def test_feature_names(self):
        self.assertListEqual(
            self.line_state.feature_names,
            [
                'station_a_mode',
                'station_a_on',
                'station_a_index_out',
                'station_b_mode',
                'station_b_on',
                'station_b_carrier',
            ]
        )

    def test_observable_feature_names(self):
        self.assertListEqual(
            self.line_state.observable_features,
            [
                'station_a_mode',
                'station_a_on',
                'station_a_index_out',
                'station_b_mode',
                'station_b_on',
            ]
        )

    def test_apply(self):
        self.line_state.apply(
            {
                'station_a': {'on': 1, 'index_out': 3},
                'station_b': {'on': 1}
            }
        )
        self.assertDictEqual(
            self.line_state.to_dict(),
            {
                'station_a_mode': 2.,
                'station_a_on': 1.0,
                'station_a_index_out': 3.,
                'station_b_mode': 0.,
                'station_b_on': 1.,
                'station_b_carrier': 0.0,
            }
        )

    def test_log(self):
        self.line_state.log()
        self.line_state.update(
            {
                'station_a': {'on': True, 'index_out': 3},
                'station_b': {'on': True}
            }
        )

        self.line_state.log()
        self.line_state.update(
            {
                'station_b': {'on': True, 'carrier': 'A'}
            }
        )
        self.line_state.log()
        df = self.line_state.df()
        self.assertIsInstance(df, pd.DataFrame)

        # Make sure all features (also non observables) are in frame
        for feature_name in self.line_state.feature_names:
            self.assertIn(feature_name, df.columns)

        np.testing.assert_array_equal(
            df['station_a_on'], [True, True, True]
        )
        np.testing.assert_array_equal(
            df['station_b_on'], [True, True, True]
        )
        pd.testing.assert_series_equal(
            df["station_b_carrier"],
            pd.Series([pd.NA, pd.NA, "A"], name="station_b_carrier"),
            check_dtype=False,
        )

    def test_values(self):
        np.testing.assert_array_equal(
            self.line_state.values,
            np.array([2., 0., 2., 0., 0., 0.])
        )

    def test_get_actions(self):
        actions = self.line_state.get_actions()
        self.assertIsInstance(actions, dict)

        self.assertEqual(len(actions['station_a']), 2)
        self.assertEqual(len(actions['station_b']), 1)

        for state in actions['station_a']:
            self.assertTrue(state.is_actionable)
        for state in actions['station_b']:
            self.assertTrue(state.is_actionable)

    def test_data(self):
        for _ in range(10):
            self.line_state.log()
        X = self.line_state.get_observations(lookback=7)

        n_features = self.line_state.data.observables.sum() + 1
        self.assertTupleEqual(X.shape, (7, n_features))

    def test_if_modes_are_represented(self):
        line = MultiProcess(n_processes=2)
        # Check if a mode is tracked for every station
        self.assertEqual(len(line.get_uptime()), 6)

    def test_uptime_calculation(self):
        line = SimpleLine()
        line.run(100)
        # since waiting_time = 10 and processing_time = 5
        # the uptime of assembly should be 33%
        self.assertAlmostEqual(line.get_uptime()[0], 0.3)
