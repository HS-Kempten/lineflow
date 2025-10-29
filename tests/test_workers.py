import unittest
import numpy as np

from lineflow.helpers import (
    compute_processing_times_of_parts,
    compute_performance_coefficient,
)
from lineflow.simulation import (
    Line,
    Sink,
    Source,
    Process,
    WorkerPool,
)


def more_to_last(state, env):
    return {
        'pool': {
            'W0': 0,
            'W1': 0,
            'W2': 0,
            'W3': 1,
            'W4': 1,
            'W5': 1,
            'W6': 1,
            'W7': 1,
            'W8': 1,
            'W9': 1,
        },
    }


def all_to_one(state, env):
    if env.now > 50 and env.now < 70:
        return {
            'pool': {
                'W0': 0,
                'W1': 0,
                'W2': 0,
                'W3': 0,
                'W4': 0,
                'W5': 0,
                'W6': 0,
                'W7': 0,
                'W8': 0,
                'W9': 0,
            },
        }

    elif env.now > 70:
        return {
            'pool': {
                'W0': 1,
                'W1': 1,
                'W2': 1,
                'W3': 1,
                'W4': 1,
                'W5': 1,
                'W6': 1,
                'W7': 1,
                'W8': 1,
                'W9': 1,
            },
        }
    else:
        return {}


def controlled_movement(state, env):

    if env.now < 50:
        return {
            'pool': {'W0': 0}
            }
    elif env.now >= 50 and env.now < 100:
        return {
            'pool': {'W0': 1}
            }
    elif env.now >= 100 and env.now < 150:
        return {
            'pool': {'W0': 0}
            }
    else:
        return {
            'pool': {'W0': 1}
            }


def shuffle_workers(state, env):
    """
    Shuffles every 20 seconds the workers
    """
    if int(env.now) % 20 == 0:
        worker_names = [a.name for a in state.get_actions()["pool"]]

        assignments = np.random.randint(2, size=10)

        return {
            'pool': dict(zip(worker_names, assignments))
        }
    else:
        return {}


class LineWithSkilledWorkers(Line):

    def __init__(self, skill_levels=None, *args, **kwargs):
        self.skill_levels = skill_levels or {}
        super().__init__(*args, **kwargs)

    def build(self):

        pool = WorkerPool(
            name='pool',
            n_workers=2,
            transition_time=2,
            skill_levels=self.skill_levels,
        )

        c1 = Source('C1', unlimited_carriers=True, position=(100, 100))
        c2 = Process('C2', worker_pool=pool, position=(200, 100))
        c3 = Process('C3', worker_pool=pool, position=(500, 100))
        c4 = Sink('C4', processing_time=2, position=(600, 100))

        c1.connect_to_output(c2)
        c2.connect_to_output(c3, transition_time=10, capacity=5)
        c3.connect_to_output(c4)



class LineWithWorkers(Line):

    def build(self):

        pool = WorkerPool(name='pool', n_workers=10, transition_time=2)

        c1 = Source('C1', unlimited_carriers=True, position=(100, 100))
        c2 = Process('C2', worker_pool=pool, position=(200, 100))
        c3 = Process('C3', worker_pool=pool, position=(500, 100))
        # Create a very slow sink to not get into dead-lock
        c4 = Sink('C4', processing_time=20, position=(600, 100))

        c1.connect_to_output(c2)
        c2.connect_to_output(c3, transition_time=10, capacity=5)
        c3.connect_to_output(c4)


class LineOneWorker(Line):
    def build(self):

        pool = WorkerPool(name='pool', n_workers=3, transition_time=5)

        c1 = Source('C1', unlimited_carriers=True, position=(100, 100))
        c2 = Process('C2', worker_pool=pool, position=(200, 100))
        c3 = Process('C3', worker_pool=pool, position=(500, 100))
        c4 = Sink('C4', processing_time=20, position=(600, 100))

        c1.connect_to_output(c2)
        c2.connect_to_output(c3, transition_time=10, capacity=5)
        c3.connect_to_output(c4)


class TestWorkers(unittest.TestCase):

    def setUp(self):
        self.line = LineWithWorkers(realtime=False, factor=0.8)
        self.worker_cols = [f"pool_W{i}" for i in range(10)]

    def test_run(self):
        self.line.run(100)
        df = self.line.get_observations()
        for i in range(10):
            self.assertIn(f'pool_W{i}', df)

    def compute_n_workers(self, df):
        for station in ['C2', 'C3']:
            df[f'{station}_n_workers'] = (df[self.worker_cols] == station).sum(axis=1)
        return df

    def test_turn_on(self):
        self.line.run(200, agent=all_to_one, visualize=False)
        df = self.line.get_observations()
        df = self.compute_n_workers(df)

        # When C3 finishes work after T=50 and before T=70, there is no worker at C3
        self.assertEqual(df[(df.T_end > 62) & (df.T_end < 70)]['C3_n_workers'].sum(), 0)
        self.assertListEqual(df[df.T_end > 80]['C3_n_workers'].unique().tolist(), [10.0])

    def test_with_random_shuffle(self):
        self.line.run(1000, agent=shuffle_workers)
        self.assertGreaterEqual(self.line.env.now, 1000)

    def test_faster_processing_with_more_worker(self):
        self.line.run(1000, agent=more_to_last)

        df_c2 = compute_processing_times_of_parts(self.line, 'C2', finished_only=True)
        df_c3 = compute_processing_times_of_parts(self.line, 'C3', finished_only=True)

        self.assertGreater(df_c2.mean()['time'], 2)
        self.assertLess(df_c3.mean()['time'], 2)

    def test_performance_coefficient(self):
        # For one worker, it should be one
        self.assertEqual(compute_performance_coefficient(1), 1)

        # It should be descending
        for i in range(100):
            self.assertGreaterEqual(
                compute_performance_coefficient(i),
                compute_performance_coefficient(i+1),
            )

        # Should always be greather than 0.0
        self.assertGreaterEqual(compute_performance_coefficient(10000), 0.0)


class TestWorkerMovement(unittest.TestCase):

    def test_without_assignment(self):
        line = LineOneWorker()
        line.run(200)
        self.assertGreaterEqual(line.env.now, 200)

    def test_worker_movement(self):
        line = LineOneWorker()
        line.run(200, agent=controlled_movement)
        df = line.get_observations()

        worker_assignment = df['pool_W0']
        self.assertListEqual(
            worker_assignment[worker_assignment != worker_assignment.shift(1)].values.tolist(),
            ['C2', 'C3', 'C2', 'C3']
        )


class TestLineWithSkilledWorkers(unittest.TestCase):

    def setUp(self):
        self.base_skill_levels = {
            'W0': {'C2': 1.0, 'C3': 1.0},
            'W1': {'C2': 1.0, 'C3': 1.0},
        }

        self.high_skill_levels = {
            'W0': {'C2': 4.0, 'C3': 4.0},
            'W1': {'C2': 4.0, 'C3': 4.0},
        }

    def test_skilled_worker_speedup(self):

        baseline_line = LineWithSkilledWorkers(skill_levels=self.base_skill_levels, random_state=42)
        baseline_line.run(500)
        df_baseline = compute_processing_times_of_parts(baseline_line, 'C3', finished_only=True)
        baseline_mean = df_baseline.mean()['time']

        skilled_line = LineWithSkilledWorkers(skill_levels=self.high_skill_levels, random_state=42)
        skilled_line.run(500)
        df_skilled = compute_processing_times_of_parts(skilled_line, 'C3', finished_only=True)
        skilled_mean = df_skilled.mean()['time']

        self.assertLess(skilled_mean, baseline_mean)
        self.assertAlmostEqual(
            baseline_mean ,
            skilled_mean * 2.0,
            delta=0.5
        )

