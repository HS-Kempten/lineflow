# Visualization

<video src="https://tobias-windisch.de/data/vids/lineflow_demo.mov"
       autoplay
       playsinline
       loop
       muted
       style="max-width:100%">
  Sorry, your browser can’t play this video.
</video>

## Drawing and Controlling Visualization

To draw a line and control its visualization in the simulation, you can use the `position` keyword for objects and the `visualize`, `realtime`, and `factor` keywords for controlling the visualization behavior.

### Using the `position` Keyword
The `position` keyword specifies the coordinates of objects (e.g., `Source`, `Sink`, `Switch`) in the simulation. These coordinates are used to draw the objects on the visualization screen. For example:

```python
source = Source(
    name='Source',
    position=(100, 300),  # X, Y coordinates
    processing_time=5,
    ...
)

sink = Sink(
    name='Sink_1',
    position=(500, 200),  # X, Y coordinates
    processing_time=10,
    ...
)
```
The `position` values determine where the objects appear on the screen. You can adjust the coordinates to arrange the layout of your line visually.

### Controlling the Visualization with Keywords:

1. `visualize`:
    - Set this to `True` when calling the run method to enable the graphical visualization of the line.
    - Example:
```python
line.run(simulation_end=200, agent=agent, visualize=True)
```

2. `realtime`:
    - Set this to `True` when initializing the Line object to make the simulation
run in real-time. This ensures that the simulation speed matches the wall-clock
time.
    - Example:
```python
line = MultiSink(realtime=True, n_sinks=5, alternate=False)
```

3. `factor`:
    - This controls the speed of the visualization when `realtime=True`. A factor of 1.0
means the simulation runs at normal speed, while a smaller value (e.g., 0.5)
slows it down, and a larger value (e.g., 2.0) speeds it up.
    - Example:
```python
line = MultiSink(realtime=True, factor=0.5, n_sinks=5, alternate=False)
```

## Example Usage
Here’s how you can combine these keywords to visualize a line:
```python
if __name__ == '__main__':
    line = MultiSink(realtime=True, factor=1.0, n_sinks=3, alternate=True)
    agent = make_greedy_policy(3)
    line.run(simulation_end=300, agent=agent, visualize=True)
```

This will:

- Arrange the objects based on their position values.
- Run the simulation in real-time (`realtime=True`).
- Display the visualization (`visualize=True`) at normal speed (`factor=1.0`).


## Zooming and Panning

Using `+` and `-` keys, you can zoom in and out of the visualization. Moreover, using the arrow
keys, you can pan around the visualization area to explore different parts of the line.
