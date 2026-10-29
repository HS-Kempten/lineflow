"""
Tests for the pygame visualization of a line.

Two layers are covered:

* ``TestVisualizationProcess`` is end-to-end. ``Line.run(visualize=True)`` and
  ``LineSimulation(render_mode="human")`` start the real visualization process,
  which renders the line while the simulation runs and shuts down with it. The
  process target is wrapped so that it reports how many frames it drew.
* ``TestHeadlessRendering`` drives the rendering pipeline in-process. A real
  line feeds payloads through a ``Communication`` pair, the real manager draws
  them onto the display surface, and the tests assert on pixels.

Neither layer needs a display. SDL's "dummy" video and audio drivers are
selected below, which is what makes the tests run in GitHub Actions. To watch
the end-to-end tests on a desktop, override the driver, e.g.
``SDL_VIDEODRIVER=cocoa python -m pytest tests/test_visualization.py``.
"""
import os
import queue
import threading
import time
import unittest
from contextlib import contextmanager
from unittest import mock

import pygame

from lineflow.examples import MultiProcess, SimpleLine
from lineflow.examples.multi_process import make_greedy_policy
from lineflow.simulation import LineSimulation
from lineflow.simulation import line as line_module
from lineflow.simulation import visualization as visu
from lineflow.simulation.connectors import Connector

# SDL reads the drivers when pygame is initialised, in this process and in the
# visualization processes, which inherit the environment.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


WHITE = pygame.Color("white")
STATION_COLORS = {"working": "green", "waiting": "yellow", "failing": "red"}


def count_pixels(surface, color):
    return pygame.mask.from_threshold(surface, pygame.Color(color), (1, 1, 1, 255)).count()


def count_non_white(surface):
    return surface.get_width() * surface.get_height() - count_pixels(surface, WHITE)


def expected_station_color(data):
    """Color a station is drawn in, given the data the line sent for it."""
    return pygame.Color(STATION_COLORS[data.mode] if data.on else "gray")

def run_visualization_instrumented(connection):
    frames = 0
    flip = pygame.display.flip

    def counting_flip():
        nonlocal frames
        if count_non_white(pygame.display.get_surface()) > 0:
            frames += 1
            if frames == 1:
                connection.send({})
        flip()

    pygame.display.flip = counting_flip
    try:
        visu.run_visualization(connection)
    finally:
        connection.send({"frames": frames})


class VisualizationAwareAgent:
    def __init__(self, line, policy, halt_after=None, timeout=60):
        self.line = line
        self.policy = policy
        self.halt_after = halt_after
        self.timeout = timeout
        self.ready_at = None
        self.started = time.monotonic()

    @property
    def ready(self):
        return self.ready_at is not None

    def __call__(self, state, env):
        if not self.ready:
            if self.line.connection.data is not None:
                self.ready_at = env.now
            elif time.monotonic() - self.started > self.timeout:
                raise AssertionError("The visualization did not draw a frame in time")
            else:
                time.sleep(0.05)
        elif self.halt_after is not None and env.now >= self.ready_at + self.halt_after:
            self.line.connection.halt_event.set()
        return self.policy(state, env)


@contextmanager
def visualization_watchdog(line, timeout):
    """
    Kills a visualization process that is still alive after ``timeout``
    seconds, so that a hang shows up as a failed exit-code assertion instead
    of a stalled CI job.
    """
    def kill():
        process = getattr(line, "visualization_process", None)
        if process is not None and process.is_alive():
            process.kill()

    timer = threading.Timer(timeout, kill)
    timer.daemon = True
    timer.start()
    try:
        yield
    finally:
        timer.cancel()


def run_visualized(line, timeout=120, **kwargs):
    """``line.run(visualize=True)`` guarded by the watchdog; shuts the process down if the run raises."""
    with visualization_watchdog(line, timeout):
        try:
            line.run(visualize=True, show_status=False, **kwargs)
        except BaseException:
            line._close_visualization()
            raise


def wait_until_drawn(line, timeout=60):
    """Blocks until the instrumented visualization has drawn its first frame."""
    deadline = time.monotonic() + timeout
    while line.connection.data is None:
        if time.monotonic() > deadline:
            raise AssertionError("The visualization did not draw a frame in time")
        time.sleep(0.05)
        line.connection.recieve_all()


def frames_drawn(line, timeout=5):
    """Frame count the instrumented visualization reported when it ended."""
    deadline = time.monotonic() + timeout
    while True:
        line.connection.recieve_all()
        data = line.connection.data
        if isinstance(data, dict) and "frames" in data:
            return data["frames"]
        if time.monotonic() > deadline:
            raise AssertionError(f"No frame report from the visualization process, got {data!r}")
        time.sleep(0.05)


class TestVisualizationProcess(unittest.TestCase):
    """The real visualization process renders a running line and shuts down with it."""

    def setUp(self):
        patcher = mock.patch.object(line_module, "run_visualization", run_visualization_instrumented)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_run_to_the_end(self):
        line = MultiProcess(n_processes=2, alternate=False)
        agent = VisualizationAwareAgent(line, make_greedy_policy(2))

        run_visualized(line, simulation_end=600, agent=agent)

        self.assertTrue(agent.ready)
        self.assertEqual(line.visualization_process.exitcode, 0)
        self.assertTrue(line.connection.stop_event.is_set())
        self.assertGreaterEqual(frames_drawn(line), 1)
        self.assertGreater(line.get_n_parts_produced(), 0)

    def test_halt_event_stops_the_line_early(self):
        line = MultiProcess(n_processes=2, alternate=False)
        agent = VisualizationAwareAgent(line, make_greedy_policy(2), halt_after=50)

        run_visualized(line, simulation_end=5_000, agent=agent)

        self.assertTrue(agent.ready)
        self.assertLess(line.env.now, 5_000)
        self.assertEqual(line.visualization_process.exitcode, 0)
        self.assertGreaterEqual(frames_drawn(line), 1)

    def test_run_without_agent(self):
        line = SimpleLine()

        run_visualized(line, simulation_end=300)

        # Nobody paces the line here, so it may finish before the process has
        # drawn anything. The process still has to start, report and exit cleanly.
        self.assertEqual(line.visualization_process.exitcode, 0)
        self.assertIsInstance(frames_drawn(line), int)

    def test_gym_environment_renders_and_restarts(self):
        env = LineSimulation(MultiProcess(n_processes=2), simulation_end=200, render_mode="human")
        with visualization_watchdog(env.line, timeout=120):
            try:
                for _ in range(2):  # the second reset restarts the visualization process
                    env.reset()
                    wait_until_drawn(env.line)
                    for _ in range(20):
                        env.step(env.action_space.sample())
            finally:
                env.close()

        self.assertEqual(env.line.visualization_process.exitcode, 0)
        self.assertGreaterEqual(frames_drawn(env.line), 1)


# ---------------------------------------------------------------------------
# In-process rendering
# ---------------------------------------------------------------------------

class HeadlessScene:
    """
    The visualization pipeline in one process.

    A line is wired to a ``Communication`` pair built on thread queues (which,
    unlike multiprocessing queues, deliver immediately), and the real manager
    renders the payloads onto the display surface one pass at a time, exactly
    as ``run_visualization`` does.
    """

    def __init__(self, line):
        self.line = line
        to_visu, to_line = queue.Queue(), queue.Queue()
        self.connection = visu.Communication(to_visu, to_line)
        line.connection = visu.Communication(to_line, to_visu, child=self.connection)
        line.connection.new_event("stop_event")
        line.connection.new_event("halt_event")
        for obj in line._objects.values():
            if isinstance(obj, Connector):
                obj.setup_positions()
        line._register_objects_at_env()

        self.screen = pygame.display.set_mode(visu.Window.size)
        self.viewport = visu.Viewport(self.screen)
        self.manager = visu.VisuManager(self.connection, self.viewport)
        self.payload = None

    def advance(self, n_steps):
        """Steps the line and ships one payload per step, as ``Line.run`` does."""
        for _ in range(n_steps):
            self.line.step()
            self.line._send_data_to_visualization()

    def render(self):
        """One pass of the ``run_visualization`` loop: receive, sync the objects, draw."""
        self.manager.receive_data()
        self.manager.heartbeat()
        if not self.viewport.is_initialized:
            self.manager.instantiate_tooltip()
            self.manager.compute_line_size()
            self.manager.instantiate_minimap()
            self.viewport.set_initial_view(line_size=self.manager.line_size)
            self.manager.tooltip.turn_off()  # tooltips get their own test
        visu.draw_scene(self.viewport, self.manager)
        self.payload = self.manager.data
        return self.screen

    def send_input(self, *events, dt=0.1):
        for event in events:
            pygame.event.post(event)
        self.manager.check_user_input(dt, self.viewport, self.connection)

    def stations(self):
        return [d for d in self.payload if d.type not in ("buffer", "carrier")]

    def carriers(self):
        return [d for d in self.payload if d.type == "carrier"]

    def to_screen(self, position):
        view, window = self.viewport.view, self.viewport.window
        return window.center + (view.offset + pygame.Vector2(position)) / view.z

    def rect(self, position, width, height):
        """Screen rectangle of an object of the given world size centred at ``position``."""
        view, window = self.viewport.view, self.viewport.window
        return pygame.Rect(
            window.center.x + (view.offset.x + position.x - width / 2) / view.z,
            window.center.y + (view.offset.y + position.y - height / 2) / view.z,
            width / view.z,
            height / view.z,
        )


class TestHeadlessRendering(unittest.TestCase):

    def setUp(self):
        pygame.init()
        self.scene = HeadlessScene(MultiProcess(n_processes=2))

    def tearDown(self):
        pygame.quit()

    def test_objects_follow_the_payload(self):
        self.scene.advance(20)
        self.scene.render()
        objects = self.scene.manager.visu_line_objects
        by_name = {d.name: d for d in self.scene.payload}
        self.assertEqual({o.name for o in objects}, set(by_name))
        for obj in objects:
            self.assertIsInstance(obj, visu.VisuManager.object_mapping[by_name[obj.name].type])
        carriers_before = {d.name for d in self.scene.carriers()}
        self.assertTrue(carriers_before)

        self.scene.advance(200)
        self.scene.render()
        carriers_after = {d.name for d in self.scene.carriers()}
        self.assertEqual({o.name for o in objects}, {d.name for d in self.scene.payload})
        self.assertTrue(carriers_before - carriers_after, "carriers that reached the sink are removed")
        self.assertTrue(carriers_after - carriers_before, "new carriers are added")

    def test_initial_view_centers_the_line_on_screen(self):
        self.scene.advance(1)
        screen = self.scene.render()
        xs = [d.position.x for d in self.scene.payload]
        ys = [d.position.y for d in self.scene.payload]
        line_center = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
        self.assertEqual(self.scene.to_screen(line_center), visu.Window.center)
        for data in self.scene.stations():
            self.assertTrue(screen.get_rect().contains(self.scene.rect(data.position, 30, 30)), data.name)

    def test_stations_are_drawn_at_their_positions_in_their_state_color(self):
        self.scene.advance(30)
        screen = self.scene.render()
        stations = self.scene.stations()
        self.assertEqual({d.name for d in stations}, {"Source", "SwitchD", "P0", "P1", "SwitchF", "Sink"})
        for data in stations:
            rect = self.scene.rect(data.position, 30, 30)
            for dx in (-6, -3, 0, 3, 6):
                pixel = (rect.centerx + dx, rect.bottom - 3)
                self.assertEqual(screen.get_at(pixel), expected_station_color(data), f"{data.name} at {pixel}")

    def test_carriers_are_drawn_with_their_fill(self):
        self.scene.advance(30)
        screen = self.scene.render()
        carriers = self.scene.carriers()
        self.assertTrue(carriers)
        for data in carriers:
            rect = self.scene.rect(data.position, 30, 10)
            self.assertEqual(screen.get_at((rect.left + 1, rect.centery)), pygame.Color("black"), data.name)
            item_color = "orange" if data.fill > 0 else "black"
            self.assertEqual(screen.get_at(rect.center), pygame.Color(item_color), data.name)

    def test_crosshair_marks_the_window_center(self):
        self.scene.advance(1)
        screen = self.scene.render()
        center = visu.Window.center
        for dx, dy in ((5, 0), (-5, 0), (0, 5), (0, -5)):
            self.assertEqual(screen.get_at((int(center.x + dx), int(center.y + dy))), pygame.Color("red"))

    def test_minimap_is_toggled_with_m(self):
        self.scene.advance(5)
        screen = self.scene.render()
        corner = (int(visu.Window.size.x) - 1, 0)  # inside the minimap frame
        self.assertEqual(screen.get_at(corner), pygame.Color("red"))

        self.scene.send_input(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_m))
        screen = self.scene.render()
        self.assertEqual(screen.get_at(corner), WHITE)

        self.scene.send_input(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_m))
        screen = self.scene.render()
        self.assertEqual(screen.get_at(corner), pygame.Color("red"))

    def test_mouse_wheel_zooms(self):
        self.scene.advance(1)
        self.scene.render()
        source = next(d for d in self.scene.payload if d.type == "source")
        zoom = self.scene.viewport.view.z

        self.scene.send_input(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=1), dt=0.1)
        self.assertGreater(self.scene.viewport.view.z, zoom)

        screen = self.scene.render()
        rect = self.scene.rect(source.position, 30, 30)
        self.assertLess(rect.width, 30)
        self.assertEqual(screen.get_at((rect.centerx, rect.bottom - 2)), expected_station_color(source))
        self.assertEqual(screen.get_at((rect.centerx, rect.bottom + 3)), WHITE)

    def test_quit_event_sets_the_halt_event_of_the_line(self):
        self.scene.advance(1)
        self.scene.render()
        self.assertFalse(self.scene.line.connection.halt_event.is_set())

        self.scene.send_input(pygame.event.Event(pygame.QUIT))
        self.assertTrue(self.scene.line.connection.halt_event.is_set())

    def test_hovering_a_station_outlines_it(self):
        self.scene.advance(1)
        self.scene.render()
        source = next(d for d in self.scene.payload if d.type == "source")
        rect = self.scene.rect(source.position, 30, 30)
        pixel = (rect.centerx, rect.bottom - 2)

        with mock.patch("pygame.mouse.get_pos", return_value=rect.center):
            self.assertEqual(self.scene.render().get_at(pixel), pygame.Color("blue"))
        self.assertEqual(self.scene.render().get_at(pixel), expected_station_color(source))

    def test_t_cycles_through_the_tooltip_states(self):
        self.scene.advance(30)
        self.scene.render()
        self.scene.manager.tooltip.turn_off()
        off = count_non_white(self.scene.render())

        counts = []
        for _ in range(2):
            self.scene.send_input(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_t))
            counts.append(count_non_white(self.scene.render()))
        # One state shows a tooltip for every object, the other only for the
        # hovered one, and the mouse rests at the origin where nothing is.
        self.assertEqual(min(counts), off)
        self.assertGreater(max(counts), off)

        self.scene.send_input(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_t))
        self.assertEqual(count_non_white(self.scene.render()), off)


class TestCommunication(unittest.TestCase):

    def test_pair_shares_events_and_keeps_the_latest_payload(self):
        parent, child = visu.setup_communication_pair()
        parent.new_event("stop_event")
        self.assertIs(parent.stop_event, child.stop_event)

        for i in range(3):
            parent.send({"i": i})
        deadline = time.monotonic() + 5
        while child.data != {"i": 2}:
            self.assertLess(time.monotonic(), deadline, "payloads did not arrive")
            time.sleep(0.01)
            child.recieve_all()
        self.assertTrue(child.new_data)

        child.recieve_all()
        self.assertFalse(child.new_data)
        self.assertEqual(child.data, {"i": 2})
