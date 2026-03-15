# Part dependence


A common challenge in manufacturing is that certain part types are processed differently based on
their characteristics resulting in different processing times. In `LineFlow`, this can be modeled
using the `carrier_specs` argument of the `Source` class, which allows you to specify different
processing times for different types of carriers and their parts. This 

## Carrier specs

Assume a production line produces components consisting two subtypes of parts, namely `Part1` and
`Part2` and that the component exists in two flavors, namely `Type_A` and `Type_B`. 

```python
carrier_specs={
    'Type_A': {
        'Part1': {
            'P1': {'extra_processing_time': 21}, 
            'P2': {'extra_processing_time': 0},
            'P3': {'extra_processing_time': 0},
        },
        'Part2': {
            'P1': {'extra_processing_time': 22}, 
            'P2': {'extra_processing_time': 0},
            'P3': {'extra_processing_time': 0},
        }
    },
    'Type_B': {
        'Part1': {
            'P1': {'extra_processing_time': 5}, 
            'P2': {'extra_processing_time': 23},
            'P3': {'extra_processing_time': 2},
        },
        'Part2': {
            'P1': {'extra_processing_time': 5}, 
            'P2': {'extra_processing_time': 24},
            'P3': {'extra_processing_time': 4},
        }
    },
},
```


Now, assume we have an assembly line implemented as follows (compare also to
[`PartdependentLine`][lineflow.examples.part_dependence.PartDependentProcessLine]:

```python

from lineflow.simulation import (
    Source,
    Sink,
    Line,
    Process,
    SequentialProcess,
)

class PartDependentLine(Line):
    def build(self):
        source = Source(
            name='Source',
            processing_time=10,
            unlimited_carriers=True,
            carrier_capacity=2,
            carrier_min_creation=10,
            carrier_specs=carrier_spec, # as defined above
        )

        p1 = Process('P1', processing_time=8)
        p2 = Process('P2', processing_time=10)
        p3 = SequentialProcess('P3', processing_time=5)
        sink = Sink('Sink')

        p1.connect_to_input(source, capacity=15)
        p2.connect_to_input(p1, capacity=15)
        p3.connect_to_input(p2, capacity=15)
        sink.connect_to_input(p3)
```


Now, the source processes in an alternating fashion carriers of `Type_A` and `Type_B`, where at
least 10 carriers of each type are created subsequently.

## Processing types of `Type_A`

At a [`Process`][lineflow.simulation.stations.Process], like `P1` and `P2`, the processing time is
determined as the processing time of the station plus the extra processing time of the part type. 

$$
\mathcal{T}_{P_1}=\underbrace{8}_{\mathrm{Station time}}+\underbrace{21}_{\text{Part1}}+\underbrace{22}_{\text{Part2}}
$$

$$
\mathcal{T}_{P_2}=\underbrace{10}_{\mathrm{Station time}}+\underbrace{0}_{\text{Part1}}+\underbrace{0}_{\text{Part2}}
$$

For [`SequentialProcess`][lineflow.simulation.stations.SequentialProcess], like `P3`, the processing
time of the station is added for each part on the carrier, i.e.:

$$
\mathcal{T}_{P_3}=\underbrace{5}_{\text{Station time}}+\underbrace{0}_{\text{Part1}}+ \underbrace{5}_{\text{Station time}}+\underbrace{0}_{\text{Part2}}
$$

## Processing types of `Type_B`

For `Type_B`, the processing times are as follows:

$$
\begin{aligned}
\mathcal{T}_{P_1}
&= \underbrace{8}_{\text{Station time}} + \underbrace{5}_{\text{Part1}} + \underbrace{5}_{\text{Part2}} \\
\mathcal{T}_{P_2}
&= \underbrace{10}_{\text{Station time}} + \underbrace{23}_{\text{Part1}} + \underbrace{24}_{\text{Part2}} \\
\mathcal{T}_{P_3}
&= \underbrace{5}_{\text{Station time}} + \underbrace{2}_{\text{Part1}} + \underbrace{5}_{\text{Station time}} + \underbrace{4}_{\text{Part2}}
\end{aligned}
$$




!!! note
    [`Assembly`][lineflow.simulation.stations.Assembly] can add additional parts which alter the
    `carrier_spec` and hence also the processing times of subsequent stations.
