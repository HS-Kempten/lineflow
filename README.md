# LineFlow

[![PyPI](https://img.shields.io/pypi/v/lineflow-rl)](https://pypi.org/project/lineflow-rl/)

`LineFLow` is a python framework to simulate assembly lines. It allows to model
arbitrary discrete part assembly lines and provides an `gymnasium` environment to
optimize them with reinforcement learning. The documentation can be
found [here](https://hs-kempten.github.io/lineflow/).

![til](docs/imgs/lineflow.gif)
# Install

Install with

```bash
pip install lineflow-rl
```

# Examples


## Visualization 
This is how an assembly line can be implemented and visualized:


```python
from lineflow.simulation import Line, Source, Sink, Process

class SimpleLine(Line):

    def build(self):

        # Set up stationary objects
        source = Source(
            name='Source',
            processing_time=5,
            position=(100, 500),
            unlimited_carriers=True,
        )

        process = Process('Process', processing_time=6, position=(350, 500))
        sink = Sink('Sink', processing_time=3, position=(600, 500))
        
        # Wire them with buffers
        source.connect_to_output(station=process, capacity=3)
        process.connect_to_output(station=sink, capacity=2)


line = SimpleLine()
line.run(simulation_end=500, visualize=True)

df = line.get_observations()
```

## Training RL agents

This is how an RL agent can be trained using `LineFlow`:

```python

from stable_baselines3 import PPO
from lineflow.simulation import LineSimulation

line = SimpleLine()
env = LineSimulation(line, simulation_end=100)
model = PPO("MlpPolicy", env)
model.learn(total_timesteps=100)
```

# Docs

Serve the docs with

```bash
mkdocs serve
```


# Paper

If you use our work in your research, please consider citing us with

```
@InProceedings{pmlr-v267-muller25c,
  title = {{L}ine{F}low: A Framework to Learn Active Control of Production Lines},
  author = {M\"{u}ller, Kai and Wenzel, Martin and Windisch, Tobias},
  booktitle = {Proceedings of the 42nd International Conference on Machine Learning},
  pages = {45212--45235},
  year = {2025},
  editor = {Singh, Aarti and Fazel, Maryam and Hsu, Daniel and Lacoste-Julien, Simon and Berkenkamp, Felix and Maharaj, Tegan and Wagstaff, Kiri and Zhu, Jerry},
  volume = {267},
  series = {Proceedings of Machine Learning Research},
  month = {13--19 Jul},
  publisher = {PMLR},
  url = {https://proceedings.mlr.press/v267/muller25c.html},
}
```

See [this README](./scripts/README.md) for more details how to run the benchmarks.


# Funding

The research behind LineFlow is funded by the Bavarian state ministry of research. Learn more
[here](https://kefis.fza.hs-kempten.de/de/forschungsprojekt/599-lineflow).
