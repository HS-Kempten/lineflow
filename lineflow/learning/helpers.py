from lineflow.simulation.environment import LineSimulation
import wandb

from stable_baselines3.common.vec_env import VecFrameStack
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.vec_env import SubprocVecEnv
from stable_baselines3.common.callbacks import BaseCallback


def make_stacked_vec_env(line, simulation_end, reward="uptime", n_envs=10, n_stack=5):

    env = make_vec_env(
        env_id=LineSimulation,
        n_envs=n_envs,
        vec_env_cls=SubprocVecEnv,
        vec_env_kwargs={
            'start_method': 'fork',
        },
        env_kwargs={
            "line": line,
            "simulation_end": simulation_end,
            "reward": reward,
        }
    )

    if n_stack > 1:

        # Stack latest observations into one
        env = VecFrameStack(env, n_stack=n_stack, channels_order='first')

    return env


class InfoLoggerCallback(BaseCallback):

    def __init__(self, info):
        super(InfoLoggerCallback, self).__init__()
        self.features = [f"{station}_{state}" for station, state in info]

    def _on_rollout_start(self):
        self.data = {f: [] for f in self.features}

    def _on_step(self):
        infos = self.locals.get('infos', [])

        for feature in self.features:
            self.data[feature].extend([info[feature] for info in infos])
        return True

    def _on_rollout_end(self):

        for feature in self.features:
            wandb.log(
                data={f"rollout/{feature}": wandb.Histogram(self.data[feature])},
                step=self.n_calls
            )
        return True
