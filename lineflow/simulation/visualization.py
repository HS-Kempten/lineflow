"""
Pygame visualization of a line.

The line runs in the main process and sends, after every step, a list of
`ConnectionData` records (one per station, buffer and carrier) through a
`Communication` channel to a second process running `run_visualization`.
Over there a `VisuManager` keeps one `VisuLineObject` per record and draws
them, together with the overlays (crosshair, minimap, tooltips), onto the
window. All coordinate conversions go through the `Viewport`.
"""
from __future__ import annotations

from multiprocessing import Event, Queue
from queue import Empty
from typing import Any, NamedTuple

import pygame


class ConnectionData:
    """Attribute bag describing one line object, sent from the line to the visualization."""

    def __init__(self, type: str, **kwargs):
        self.type = type
        self.__dict__.update(kwargs)

    def __getattr__(self, name: str) -> Any:
        # Only reached for fields that were not sent. Declaring it tells type
        # checkers that a record carries arbitrary fields.
        raise AttributeError(name)

    def __repr__(self):
        fields = ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items() if k != "type")
        return f"{self.type}({fields})"


class Communication:
    """
    One end of the channel between the line and the visualization process.

    Both ends share the two queues (crosswise) and the two events: `stop_event`
    ends the visualization process, `halt_event` asks the line to stop the
    simulation (it is set when the window is closed).
    """

    def __init__(self, queue_in, queue_out, stop_event, halt_event):
        self.queue_in = queue_in
        self.queue_out = queue_out
        self.stop_event = stop_event
        self.halt_event = halt_event

    def send(self, data) -> None:
        self.queue_out.put(data)

    def receive_latest(self):
        """Drains the incoming queue and returns the newest item, or None if nothing arrived."""
        latest = None
        while True:
            try:
                latest = self.queue_in.get_nowait()
            except Empty:
                return latest

    def close(self) -> None:
        """
        Lets this process exit although the other end may never consume what
        was sent (otherwise the queue's feeder thread blocks the interpreter).
        """
        self.queue_out.cancel_join_thread()


def setup_communication_pair():
    """Returns the line's and the visualization's end of a new channel."""
    to_visualization, to_line = Queue(), Queue()
    stop_event, halt_event = Event(), Event()
    line_end = Communication(to_line, to_visualization, stop_event, halt_event)
    visualization_end = Communication(to_visualization, to_line, stop_event, halt_event)
    return line_end, visualization_end


def mouse_position() -> pygame.Vector2:
    return pygame.Vector2(pygame.mouse.get_pos())


class Window:
    size = pygame.Vector2(1280, 720)
    center = size / 2


class View:
    """
    Camera of the viewport: the world point `-offset` is drawn at the window
    centre, and world lengths are divided by the zoom `z`.
    """

    z_min = 0.5
    z_max = 10

    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = 1.0):
        self.offset = pygame.Vector2(x, y)
        self.z = z

    def zoom(self, factor: float) -> None:
        self.z = max(self.z_min, min(self.z_max, self.z * factor))


class LineBounds(NamedTuple):
    width: float
    height: float
    center: pygame.Vector2


def compute_line_bounds(objects) -> LineBounds:
    """Bounding box of the positions of the given line objects."""
    xs = [obj.position.x for obj in objects]
    ys = [obj.position.y for obj in objects]
    upper_left = pygame.Vector2(min(xs), min(ys))
    size = pygame.Vector2(max(xs), max(ys)) - upper_left
    return LineBounds(size.x, size.y, upper_left + size / 2)


class Viewport:
    """Maps world coordinates of the line to pixels of the window."""

    def __init__(self, screen: pygame.Surface):
        self.window = Window
        self.screen = screen
        self.view = View()  # identity until `set_initial_view` fits the line

    def set_initial_view(self, bounds: LineBounds, margin: int = 100) -> None:
        """Centres the line and zooms out until it fits the window with a margin."""
        scalar = max(
            bounds.width / (self.window.size.x - margin),
            bounds.height / (self.window.size.y - margin),
        )
        z = 1 if scalar < 1 else round(scalar, 1)
        self.view = View(-bounds.center.x, -bounds.center.y, z)

    def to_screen(self, point) -> pygame.Vector2:
        return self.window.center + (self.view.offset + point) / self.view.z

    def px(self, length):
        """World length (or vector) in pixels."""
        return length / self.view.z

    def rect(self, center, width: float, height: float) -> pygame.Rect:
        """Screen rectangle of a world box of the given size centred at `center`."""
        size = pygame.Vector2(width, height)
        return pygame.Rect(self.to_screen(center - size / 2), self.px(size))


class TooltipInfo(NamedTuple):
    value: float
    anchor: pygame.Vector2
    color: str
    history: list[float] | None = None


class VisuObject:
    """Anything the scene draws. Objects are drawn in ascending `layer` order."""

    layer = 0

    def draw(self, viewport: Viewport) -> None:
        raise NotImplementedError()


class Crosshair(VisuObject):
    layer = 3
    size = 10
    color = "red"

    def __init__(self, position):
        self.position = pygame.Vector2(position)

    def draw(self, viewport: Viewport) -> None:
        for arm in (pygame.Vector2(self.size, 0), pygame.Vector2(0, self.size)):
            pygame.draw.line(viewport.screen, self.color, self.position + arm, self.position - arm)


class MiniMap(VisuObject):
    """Scaled-down drawing of the line objects in the top right corner, with the current view outlined."""

    layer = 4
    color = "red"
    border = pygame.Vector2(2, 2)
    margin = pygame.Vector2(10, 10)

    def __init__(self, objects: dict[str, VisuLineObject], scale: float = 0.3):
        self.objects = objects  # the manager's live dict
        self.active = True
        self.scale = scale
        self.fit(LineBounds(0, 0, pygame.Vector2()))

    def fit(self, bounds: LineBounds) -> None:
        """Sizes the map so that the line fits in and places it in the top right corner."""
        self.size = pygame.Vector2(bounds.width, bounds.height) * self.scale + self.margin * 2
        self.offset = self.size / 2 - bounds.center * self.scale
        self.position = pygame.Vector2(Window.size.x - self.size.x - self.border.x, self.border.y)
        self.surface = pygame.Surface(self.size)

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(self.position - self.border, self.size + self.border * 2)

    def toggle(self) -> None:
        self.active = not self.active

    def to_map(self, point) -> pygame.Vector2:
        """World point in pixels of the minimap surface."""
        return self.offset + point * self.scale

    def draw_view_outline(self, viewport: Viewport) -> None:
        view = viewport.view
        size = viewport.window.size * self.scale * view.z
        top_left = self.offset - size / 2 - view.offset * self.scale
        pygame.draw.rect(self.surface, self.color, pygame.Rect(top_left, size), width=1)
        pygame.draw.circle(self.surface, self.color, self.offset - view.offset * self.scale, 3, width=1)

    def draw(self, viewport: Viewport) -> None:
        if not self.active:
            return
        self.surface.fill("white")
        for obj in sorted(self.objects.values(), key=lambda obj: obj.layer):
            obj.draw_simple(self)
        self.draw_view_outline(viewport)
        pygame.draw.rect(viewport.screen, self.color, self.rect)
        viewport.screen.blit(self.surface, self.position)


class Tooltip(VisuObject):
    """
    Tooltip layer, drawn last. It shows the value of every object (`all`),
    of the object under the mouse (`hovered`), or nothing (`off`).
    """

    layer = 5
    states = ("hovered", "all", "off")

    def __init__(self, objects: dict[str, VisuLineObject]):
        self.objects = objects  # the manager's live dict
        self.state_index = 0

    @property
    def state(self) -> str:
        return self.states[self.state_index]

    def cycle_state(self) -> None:
        self.state_index = (self.state_index + 1) % len(self.states)

    def turn_off(self) -> None:
        self.state_index = self.states.index("off")

    @staticmethod
    def draw_box(surface, rect: pygame.Rect, border_color="black") -> None:
        pygame.draw.rect(surface, "white", rect, border_radius=8)
        pygame.draw.rect(surface, border_color, rect, width=1, border_radius=8)

    def draw_number(self, surface, number, pos, text_color="black") -> None:
        font = pygame.font.SysFont(None, 20)
        text = font.render(str(number), True, text_color)
        rect = text.get_rect(left=pos.x - 30, top=pos.y - 20)
        self.draw_box(surface, rect.inflate(4, 4))
        surface.blit(text, rect)

    def draw_history(self, surface, values, pos, color="blue") -> None:
        """Plots the values, min-max normalised, as a small dot graph."""
        frame = pygame.Rect(pos.x + 10, pos.y - 10, 100, 50)
        self.draw_box(surface, frame.inflate(8, 8))
        high, low = max(values) * 1.05, min(values) * 0.95
        for i, value in enumerate(values):
            factor = 1 if high == 0 else 1 - (value - low) / (high - low)
            pygame.draw.circle(surface, color, pos + (i + 10, frame.height * factor - 10), 1)

    def draw_info(self, surface, info: TooltipInfo, pos, text_color, history_color) -> None:
        self.draw_number(surface, info.value, pos, text_color)
        if info.history:
            self.draw_history(surface, info.history, pos, history_color)

    def draw(self, viewport: Viewport) -> None:
        if self.state == "off":
            return
        # Top layer first, so that a carrier wins over the buffer below it
        for obj in sorted(self.objects.values(), key=lambda obj: obj.layer, reverse=True):
            info = obj.tooltip(viewport)
            if info is None:
                continue
            if self.state == "all":
                self.draw_info(viewport.screen, info, info.anchor, info.color, info.color)
            elif obj.is_hovered(viewport):
                self.draw_info(viewport.screen, info, mouse_position(), "black", "blue")
                return


class VisuLineObject(VisuObject):
    """
    Counterpart of a simulation object. `update` applies the data the line
    sent; the constructor applies it for the first time.
    """

    color = "gray"
    width = 0
    height = 0

    def __init__(self, data: ConnectionData):
        self.name = data.name
        self.update(data)

    def update(self, data: ConnectionData) -> None:
        self.position = pygame.Vector2(data.position)

    def rect(self, viewport: Viewport) -> pygame.Rect:
        return viewport.rect(self.position, self.width, self.height)

    def is_hovered(self, viewport: Viewport) -> bool:
        return self.rect(viewport).collidepoint(pygame.mouse.get_pos())

    def tooltip(self, viewport: Viewport) -> TooltipInfo | None:
        """What the tooltip layer shows for this object, or None."""
        return None

    def draw_simple(self, minimap: MiniMap) -> None:
        raise NotImplementedError()


class VisuStation(VisuLineObject):
    layer = 1
    width = 30
    height = 30
    radius = 8
    mode_colors = {"working": "green", "waiting": "yellow", "failing": "red"}
    history_length = 100
    marker_direction = None  # +1 draws a triangle pointing down, -1 pointing up

    def __init__(self, data: ConnectionData):
        self.processing_times = []
        super().__init__(data)

    def update(self, data: ConnectionData) -> None:
        super().update(data)
        self.mode = data.mode
        self.on = data.on
        self.worker_skill = getattr(data, "worker_skill", None)
        self.processing_times.append(round(float(data.processing_time), 1))
        del self.processing_times[:-self.history_length]

    @property
    def station_color(self) -> str:
        return self.mode_colors[self.mode] if self.on else self.color

    def draw_block(self, viewport: Viewport) -> None:
        pygame.draw.rect(
            viewport.screen,
            self.station_color,
            self.rect(viewport),
            border_radius=int(max(1, viewport.px(self.radius))),
        )

    def draw_name(self, viewport: Viewport) -> None:
        font = pygame.font.SysFont(None, int(viewport.px(20)))
        text = font.render(self.name, True, "black")
        center = viewport.to_screen(self.position + (0, -0.7 * self.height))
        viewport.screen.blit(text, text.get_rect(center=center))

    def draw_label(self, viewport: Viewport, text: str) -> None:
        font = pygame.font.SysFont(None, int(viewport.px(14)))
        label = font.render(text, False, "black")
        viewport.screen.blit(label, label.get_rect(center=self.rect(viewport).center))

    def draw_outline(self, viewport: Viewport) -> None:
        pygame.draw.rect(
            viewport.screen,
            "blue",
            self.rect(viewport),
            width=int(max(1, viewport.px(self.width / 10))),
            border_radius=int(max(1, viewport.px(self.radius))),
        )

    def draw_marker(self, viewport: Viewport, direction: int) -> None:
        center = pygame.Vector2(self.rect(viewport).center)
        corners = (
            pygame.Vector2(0, direction * self.height / 4),
            pygame.Vector2(self.width / 4, -direction * self.height / 5),
            pygame.Vector2(-self.width / 4, -direction * self.height / 5),
        )
        pygame.draw.polygon(viewport.screen, "black", [center + viewport.px(corner) for corner in corners])

    def draw(self, viewport: Viewport) -> None:
        self.draw_block(viewport)
        self.draw_name(viewport)
        if self.worker_skill is not None:
            self.draw_label(viewport, f"W={self.worker_skill}")
        if self.marker_direction is not None:
            self.draw_marker(viewport, self.marker_direction)
        if self.is_hovered(viewport):
            self.draw_outline(viewport)

    def draw_simple(self, minimap: MiniMap) -> None:
        pygame.draw.circle(
            minimap.surface,
            self.station_color,
            minimap.to_map(self.position),
            int(self.height / 2 * minimap.scale),
        )

    def tooltip(self, viewport: Viewport) -> TooltipInfo | None:
        if not self.processing_times:
            return None
        anchor = pygame.Vector2(self.rect(viewport).topright)
        return TooltipInfo(self.processing_times[-1], anchor, "darkgreen", self.processing_times)


class VisuSwitch(VisuStation):
    connector_color = "gray"

    def update(self, data: ConnectionData) -> None:
        super().update(data)
        self.pos_in, self.pos_out = (pygame.Vector2(pos) for pos in data.pos_in_out)

    def draw_connections(self, viewport: Viewport) -> None:
        center = viewport.to_screen(self.position)
        width = int(viewport.px(10))
        pygame.draw.circle(viewport.screen, self.connector_color, center, viewport.px(self.width / 4))
        pygame.draw.line(viewport.screen, self.connector_color, viewport.to_screen(self.pos_in), center, width=width)
        pygame.draw.line(viewport.screen, self.connector_color, center, viewport.to_screen(self.pos_out), width=width)

    def draw(self, viewport: Viewport) -> None:
        super().draw(viewport)
        self.draw_connections(viewport)


class VisuMagazine(VisuStation):
    def update(self, data: ConnectionData) -> None:
        super().update(data)
        self.magazine = data.magazine

    def draw(self, viewport: Viewport) -> None:
        super().draw(viewport)
        self.draw_label(viewport, f"C={self.magazine}")


class VisuSource(VisuStation):
    marker_direction = -1


class VisuSink(VisuStation):
    marker_direction = 1


class VisuConnector(VisuLineObject):
    layer = 0
    width = 10

    def update(self, data: ConnectionData) -> None:
        super().update(data)
        self.endpoint = pygame.Vector2(data.endpoint)

    def center(self, viewport: Viewport) -> pygame.Vector2:
        return viewport.to_screen((self.position + self.endpoint) / 2)

    def is_hovered(self, viewport: Viewport) -> bool:
        mouse = mouse_position()
        start, end = viewport.to_screen(self.position), viewport.to_screen(self.endpoint)
        half_width = viewport.px(self.width) / 2
        line = end - start
        length_sq = line.magnitude_squared()
        if length_sq == 0:
            return (mouse - start).magnitude() <= half_width
        t = (mouse - start).dot(line) / length_sq
        distance = abs((mouse - start).cross(line)) / length_sq**0.5
        return 0 <= t <= 1 and distance <= half_width

    def draw(self, viewport: Viewport) -> None:
        pygame.draw.line(
            viewport.screen,
            self.color,
            viewport.to_screen(self.position),
            viewport.to_screen(self.endpoint),
            width=int(viewport.px(self.width)),
        )

    def draw_simple(self, minimap: MiniMap) -> None:
        pygame.draw.line(
            minimap.surface,
            self.color,
            minimap.to_map(self.position),
            minimap.to_map(self.endpoint),
            width=int(self.width * minimap.scale),
        )


class VisuBuffer(VisuConnector):
    def update(self, data: ConnectionData) -> None:
        super().update(data)
        self.capacity = data.capacity
        self.fill = round(float(data.fill), 2)

    def draw_slots(self, viewport: Viewport) -> None:
        step = (self.endpoint - self.position) / (self.capacity + 1)
        for n in range(1, self.capacity + 1):
            pygame.draw.circle(
                viewport.screen,
                self.color,
                viewport.to_screen(self.position + step * n),
                int(viewport.px(self.width)),
            )

    def draw(self, viewport: Viewport) -> None:
        super().draw(viewport)
        self.draw_slots(viewport)

    def tooltip(self, viewport: Viewport) -> TooltipInfo:
        return TooltipInfo(self.fill, self.center(viewport), "darkgray")


class VisuCarrier(VisuLineObject):
    layer = 2
    color = "black"
    item_color = "orange"
    width = 30
    height = 10
    border = 2

    def update(self, data: ConnectionData) -> None:
        super().update(data)
        self.fill = round(float(data.fill), 2)

    def items_rect(self, viewport: Viewport) -> pygame.Rect:
        """Inner part of the carrier, filled from the left according to `fill`."""
        border = 2 * viewport.px(self.border)
        inner = self.rect(viewport).inflate(-border, -border)
        return pygame.Rect(inner.left, inner.top, inner.width * self.fill, inner.height)

    def draw_name(self, viewport: Viewport) -> None:
        font = pygame.font.SysFont(None, int(viewport.px(20)))
        text = font.render(self.name, False, "blue")
        center = viewport.to_screen(self.position + (0, +1.3 * self.height))
        viewport.screen.blit(text, text.get_rect(center=center))

    def draw(self, viewport: Viewport) -> None:
        pygame.draw.rect(viewport.screen, self.color, self.rect(viewport))
        pygame.draw.rect(viewport.screen, self.item_color, self.items_rect(viewport))
        if self.is_hovered(viewport):
            self.draw_name(viewport)

    def draw_simple(self, minimap: MiniMap) -> None:
        pygame.draw.circle(
            minimap.surface,
            self.item_color,
            minimap.to_map(self.position),
            int(self.width / 3 * minimap.scale),
        )

    def tooltip(self, viewport: Viewport) -> TooltipInfo:
        return TooltipInfo(self.fill, pygame.Vector2(self.rect(viewport).midtop), "orange")


class VisuManager:
    """Keeps the visual objects in sync with the data the line sends, draws the scene and handles input."""

    object_mapping = {
        "station": VisuStation,
        "process": VisuStation,
        "source": VisuSource,
        "sink": VisuSink,
        "assembly": VisuStation,
        "magazine": VisuMagazine,
        "switch": VisuSwitch,
        "buffer": VisuBuffer,
        "carrier": VisuCarrier,
    }

    def __init__(self, connection: Communication, viewport: Viewport):
        self.connection = connection
        self.viewport = viewport
        self.objects: dict[str, VisuLineObject] = {}  # shared with the minimap and the tooltip layer
        self.crosshair = Crosshair(viewport.window.center)
        self.minimap = MiniMap(self.objects)
        self.tooltip = Tooltip(self.objects)
        self.is_initialized = False

    def sync(self, payload) -> None:
        """Updates, creates and removes objects so that they match the records the line sent."""
        incoming = {data.name: data for data in payload}
        for name in list(self.objects):
            if name not in incoming:
                del self.objects[name]
        for name, data in incoming.items():
            if name in self.objects:
                self.objects[name].update(data)
            else:
                self.objects[name] = self.object_mapping[data.type](data)

    def initialize(self) -> None:
        """Fits the view and the minimap to the line; needs at least one object."""
        bounds = compute_line_bounds(self.objects.values())
        self.viewport.set_initial_view(bounds)
        self.minimap.fit(bounds)
        self.is_initialized = True

    @property
    def drawables(self):
        """All objects of the scene, background first."""
        objects = [*self.objects.values(), self.crosshair, self.minimap, self.tooltip]
        return sorted(objects, key=lambda obj: obj.layer)

    def draw_scene(self) -> None:
        self.viewport.screen.fill("white")
        for obj in self.drawables:
            obj.draw(self.viewport)

    def check_user_input(self, dt: float) -> None:
        view = self.viewport.view
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.connection.halt_event.set()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_m:
                    self.minimap.toggle()
                if event.key == pygame.K_t:
                    self.tooltip.cycle_state()
            elif event.type == pygame.MOUSEWHEEL:
                view.zoom(1 + 5 * event.y * dt)

        mouse_rel = pygame.Vector2(pygame.mouse.get_rel())
        if pygame.mouse.get_pressed(num_buttons=3)[0]:
            view.offset += mouse_rel * view.z

        keys = pygame.key.get_pressed()
        pan = 300 * view.z * dt
        if keys[pygame.K_q]:
            view.zoom(1 - 3 * dt)
        if keys[pygame.K_e]:
            view.zoom(1 + 3 * dt)
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            view.offset.y += pan
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            view.offset.y -= pan
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            view.offset.x += pan
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            view.offset.x -= pan
        if keys[pygame.K_h] and keys[pygame.K_LSHIFT]:
            self.connection.halt_event.set()


def run_visualization(connection: Communication) -> None:
    pygame.init()
    screen = pygame.display.set_mode(Window.size)
    clock = pygame.time.Clock()
    dt = 0
    manager = VisuManager(connection, Viewport(screen))
    try:
        while not connection.stop_event.is_set():
            if manager.is_initialized:
                manager.check_user_input(dt)

            payload = connection.receive_latest()
            if payload is not None:
                manager.sync(payload)
            if not manager.is_initialized and manager.objects:
                manager.initialize()

            if manager.is_initialized:
                manager.draw_scene()
            if connection.halt_event.is_set():
                screen.fill("white")

            pygame.display.flip()
            dt = clock.tick(60) / 1000
    finally:
        pygame.quit()
        connection.stop_event.set()
