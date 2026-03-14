# Waiting Time

## Without jumps

<video src="https://tobias-windisch.de/data/vids/lineflow_waitingtime.mov"
       autoplay
       playsinline
       loop
       muted
       style="max-width:100%">
  Sorry, your browser can’t play this video.
</video>

In this scenario, the goal is to determine the optimal waiting time between 
parts produced by a source station, shown in the image as S_main​. This station, 
along with another source S_component, supplies an assembly station, displayed 
as Assembly, which combines components from both sources to produce the final 
product. Once assembled, the product moves to the Sink.

A key challenge is that components from the component source have a limited 
lifespan, known as the assembly condition. If too much time passes between the 
moment a component is prepared at the source and when the assembly process 
begins at the assembly, the component becomes unusable. In such cases, the 
assembly must discard the expired component and wait for a replacement. This 
not only increases costs but also disrupts the workflow, as defective 
components must be removed before the assembly can continue. This issue is 
common in processes like adhesive bonding, where adhesives can dry out if 
not applied within a specific timeframe.

If the waiting time between parts is too short, the source produces excess 
components that the assembly cannot process in time, leading to unnecessary 
waste. Conversely, if the waiting time is too long, the assembly is left 
waiting for components, delaying production. The objective is to find a 
balance that ensures a steady supply of components at the assembly while 
minimizing waste and inefficiencies.

Since the assembly is assumed to be the bottleneck in the system, the overall 
production rate depends on how quickly this station can receive components, 
assemble them, and move the assembled product to the next buffer. The optimal 
waiting time should match the pace at which the assembly and the source process 
and handle parts to maintain a continuous and efficient workflow.

### What is optimized?
The processing times of the source station and the assembly station follow 
specific distributions. Similarly, the time required to move a component into 
and out of a buffer (put and get time) also follows distinct distributions. The 
goal is to determine the optimal waiting time at the component source, which must 
account for the difference between the time required by the assembly to complete 
processing and the time required by source to prepare its components. Essentially, 
the waiting time must bridge this gap to ensure a smooth workflow. By optimizing 
the waiting time of the component source, the earned reward (i.e. produced parts) 
can be maximized.

### Optimization using Lineflow
We used Lineflow to optimize the production line described above. To achieve this, 
we implemented A2C, PPO, Recurrent PPO, and TRPO algorithms. The maximum reward 
achieved was slightly below 160, with all algorithms successfully optimizing the waiting 
time and improving the reward. An explanation for the maximum reward this line can produce
is given in the following paragraph.
![Waiting time rl reward](../imgs/rl_benchmark_waiting_time_reward.png)


## Verification of the optimization
In this scenario, learning a fixed waiting time is sufficient to optimize production 
efficiency. The image shown below illustrates how different waiting times at the 
component source impact overall system performance, i.e. the reward.
Using the parameters mentioned above, the optimum waiting time for the line is 18.5. 
If this waiting time is chosen, the line can obtain a reward averaging nearly 160. 
Therefore, all algorithms used can optimize the line sufficiently.
For a detailed calculation and proof of the optimal waiting time, see *(Link to Lineflow paper)*.
![Waiting time optimum](../imgs/waiting_time_optimum.png)
## With time jumps

<video src="https://tobias-windisch.de/data/vids/lineflow_waitingtime.mov"
       autoplay
       playsinline
       loop
       muted
       style="max-width:100%">
  Sorry, your browser can’t play this video.
</video>

To further explore dynamic adjustments in waiting times, we introduce a variation 
called Waiting Time Jump. In this scenario, the processing time at the assembly 
changes unexpectedly at a randomly selected moment within the simulation. During 
a predefined time window, the processing time at the assembly increases, affecting 
the overall assembly process. A visualization of these processing time variations 
across multiple simulations is provided in the figure below.
![Waiting time jump](../imgs/waiting_time_jump_processing_times.png)

Since the exact timing and duration of these jumps *T<sub>jump</sub>* vary, the 
maximum possible output fluctuates as well. 
To ensure fair comparisons between agents, we construct the 
new assembly time based on *T<sub>jump</sub>*,​ so that the maximum possible reward 
remains constant. Specifically, we define a constant value *R* between 0.5 and 1.0 
and set a factor *f* so that the expected maximum number of produced parts is *R⋅N*, 
where *N* is the expected number of parts produced in the standard waiting time 
scenario without jumps. 

### What is optimized?
A well-designed control strategy must adapt to these changes in real time. 
When the processing time changes, the agent only becomes aware of 
it after the first part is completed under the new conditions. When the processing 
time at the assembly suddenly increases, the system may initially 
continue operating with an outdated waiting time, resulting in expired components. 
Similarly, when the processing time decreases, the waiting time may be too long, 
causing unnecessary delays. The challenge for an adaptive control agent is to detect 
these changes as early as possible and adjust the waiting time accordingly.
If these changes to the assembly time are taken into account as quickly as possible, 
the waiting time can be optimized so that the reward is maximized.


### Optimization using Lineflow
Our line can achieve a maximum reward of 115, with the RecurrentPPO algorithm 
performing best. This method achieves an average reward of up to 106. The A2C 
algorithm achieves an average reward of over 100, although the other methods do not 
reach these results.
![Waiting time jump LineFlow](../imgs/rl_benchmark_waiting_time_jump_reward.png)


### Verification of the optimization

To assess the effectiveness of different control strategies, we evaluate how well 
an agent can learn and adapt to these shifts based on observed processing times. 
By continuously updating its estimates of how long assembly takes, the agent can 
optimize waiting times to maintain a stable and efficient production flow.

To develop an optimal strategy for WTJ, we estimate the processing time based on 
past observations. Specifically, we track the processing times reported from 
the assembly station and compute a rolling average over recent observations. 
A longer tracking period provides a more stable estimate but slows the agent’s 
ability to detect sudden jumps.

By testing different tracking periods, we found that using only the most recent 
observation allows the agent to respond the fastest, leading to the highest reward, as
shown in the figure below.
This optimized performance is used as the maximum possible reward (115) for our line.
![Waiting time jump heuristics](../imgs/waiting_time_jump_heuristics.png)


## Code
```python
--8<-- "lineflow/examples/waiting_time.py"
```
