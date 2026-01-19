import unittest
import numpy as np
from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3 import PPO
from sb3_contrib import RecurrentPPO

from lineflow.simulation import (
    Source,
    Line,
)
from lineflow.simulation.states import (
    DiscreteState,
    ObjectStates,
    TokenState,
    LineStates,
)

from lineflow.examples import MultiProcess
from lineflow.learning.helpers import make_stacked_vec_env
from lineflow.simulation.environment import (
    LineSimulation,
    _build_action_space,
    _build_observation_space,
)


class EnvMock(object):

    def __init__(self):
        self.time = 0

    def now(self):
        self.time = self.time + 1
        return self.time


class TestActionBounding(unittest.TestCase):
    def setUp(self):
        class MockSource(Source):
            def init_state(self):
                self.state = ObjectStates(
                    DiscreteState('waiting_time', categories=[2, 3, 4], is_actionable=self.actionable_waiting_time),
                    DiscreteState('test', categories=[10, 11], is_actionable=self.actionable_waiting_time),
                    DiscreteState('on', categories=[True, False], is_actionable=False, is_observable=False),
                )

                self.state['on'].update(True)

        class LineMock(Line):
            def build(self):
                source = MockSource('S')

        self.line = LineMock()

    def test_boundaries(self):
        space = _build_action_space(self.line.state)
        self.assertListEqual(list(space.nvec), [3, 2])

    def test_apply_action(self):
        action = {
            "S": {"test": 1}
        }
        self.line.apply(action)
        self.assertEqual(self.line.state.objects["S"]["test"].to_str(), 11)


class TestAssemblyLine(unittest.TestCase):

    def setUp(self):
        self.line = MultiProcess(alternate=False, n_processes=4)

    def test_compatibility_with_stable_baselines(self):
        check_env(LineSimulation(self.line, simulation_end=100))

    def test_training(self):
        env = LineSimulation(self.line, simulation_end=100)
        model = PPO("MlpPolicy", env)
        model.learn(total_timesteps=100)

    def test_with_stacked_environment(self):
        env = make_vec_env(
            env_id=LineSimulation,
            n_envs=5,
            env_kwargs={
                "line": MultiProcess(alternate=False, n_processes=3),
                "simulation_end": 100,
            }
        )
        model = PPO("MlpPolicy", env)
        model.learn(total_timesteps=100)

    def test_with_recurrent_ppo(self):
        env = make_vec_env(
            env_id=LineSimulation,
            n_envs=5,
            env_kwargs={
                "line": MultiProcess(alternate=False, n_processes=3),
                "simulation_end": 100,
            }
        )
        model = RecurrentPPO("MlpLstmPolicy", env)
        model.learn(total_timesteps=100)

    def test_reward_with_random_agent(self):
        env = LineSimulation(self.line, simulation_end=100)
        obs = env.reset()
        n_steps = 100
        rewards = []
        for _ in range(n_steps):
            # Random action
            action = env.action_space.sample()
            _, reward, _, _, _ = env.step(action)
            rewards.append(reward)

        self.assertEqual(sum(rewards), self.line.get_n_parts_produced() - self.line.get_n_scrap_parts())

    def test_sparse_reward(self):
        env = LineSimulation(self.line, simulation_end=1_000, reward="parts-sparse")
        rewards = []
        done = False
        env.reset()
        while not done:
            action = env.action_space.sample()
            _, reward, terminated, truncated, _= env.step(action)
            done = terminated or truncated
            rewards.append(reward)

        self.assertEqual(sum(rewards[:-1]), 0)
        self.assertEqual(rewards[-1], self.line.get_n_parts_produced())

    def test_exception_on_unkown_reward(self):
        with self.assertRaises(AssertionError):
            LineSimulation(self.line, simulation_end=100, reward="unknown_reward")

class TestSpaceBuilding(unittest.TestCase):

    def setUp(self):
        station_a = ObjectStates(
            DiscreteState('mode', categories=['waiting', 'working', 'error']),
            DiscreteState('on', categories=[True, False], is_actionable=True),
            DiscreteState('index_out', categories=[0, 1, 2, 3], is_actionable=True),
        )
        station_b = ObjectStates(
            DiscreteState('mode', categories=['waiting', 'working', 'error']),
            DiscreteState('on', categories=[True, False], is_actionable=True),
            TokenState('carrier', is_actionable=False, is_observable=False)
        )

        self.line_state = LineStates(
            objects={
                'station_a': station_a,
                'station_b': station_b,
            },
            env=EnvMock()
        )

        self.line_state.update(
            {
                "station_b": {
                    'mode': 'waiting',
                    'on': True,
                    'carrier': "abc",
                },
                "station_a": {
                    'mode': 'error',
                    'on': True,
                    'index_out': 2
                }
            }
        )
        self.line_state.log()

    def test_build_action_space(self):
        space = _build_action_space(self.line_state)
        self.assertTupleEqual(space.shape, (3,))

    def test_build_observation_space(self):
        space = _build_observation_space(self.line_state)
        self.assertTupleEqual(space.shape, (1, 5))
        np.testing.assert_array_equal(
            space.high,
            np.array([
                [2.0, 1.0, 3.0, 2.0, 1.0],
            ]),
        )

    def test_vectorizing_and_stacking(self):
        line = MultiProcess(alternate=False, n_processes=3)

        n_envs = 10
        n_stack = 7
        n_features = len(line.state.observable_features)

        env = make_stacked_vec_env(
            line=line,
            simulation_end=100,
            n_envs=n_envs,
            n_stack=n_stack)

        obs = env.reset()
        self.assertTupleEqual(
            obs.shape,
            (n_envs, n_stack, n_features)
        )
