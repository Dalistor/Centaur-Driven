"""Small CPU renderer: an extruded archer, lighting, depth and Unicode Braille.

No terminal I/O or dependencies live here. One cached mesh is projected into a
bounded 2 × 4 dot grid; the view owns colors and writes the resulting cells.
"""

from dataclasses import dataclass
from functools import lru_cache
import math

FRAME_SECONDS = 0.05
SPIN_SECONDS = 6.0
MAX_COLUMNS, MAX_ROWS = 36, 16
GRID = 112
EXTENT = 1.05
STEP = EXTENT * 2 / (GRID - 1)
DOT_BITS = ((1, 8), (2, 16), (4, 32), (64, 128))


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * t * (t * (t * 6 - 15) + 10)


def polygon(x, y, vertices):
    inside = False
    previous = vertices[-1]
    for point in vertices:
        ax, ay = previous
        bx, by = point
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
            inside = not inside
        previous = point
    return inside


def stroke(x, y, points, radius):
    for (ax, ay), (bx, by) in zip(points, points[1:]):
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
        if (x - ax - t * dx) ** 2 + (y - ay - t * dy) ** 2 <= radius ** 2:
            return True
    return False


# Original vector silhouette: equine body, four separate legs, human torso,
# drawn arm, head in profile, longbow and the Centaur's green arrow.
BODY = (
    ((-.64, .13), (-.45, .04), (-.18, .10), (.04, .08), (.06, -.10),
     (.02, -.31), (.13, -.45), (.28, -.43), (.34, -.27), (.32, -.06),
     (.38, .15), (.37, .31), (.19, .43), (-.23, .38), (-.53, .40), (-.66, .29)),
    ((-.60, .30), (-.43, .34), (-.47, .54), (-.63, .72), (-.67, .88),
     (-.79, .88), (-.74, .65), (-.59, .48)),
    ((-.38, .34), (-.26, .36), (-.21, .56), (-.27, .79), (-.19, .87),
     (-.34, .88), (-.37, .78), (-.32, .55)),
    ((.10, .35), (.22, .34), (.18, .59), (.29, .77), (.39, .82),
     (.39, .88), (.23, .88), (.07, .62)),
    ((.27, .28), (.37, .27), (.48, .46), (.48, .61), (.40, .68),
     (.31, .65), (.38, .57), (.36, .48), (.23, .40)),
    ((.12, -.61), (.27, -.61), (.29, -.46), (.22, -.40), (.12, -.45)),
    ((.14, -.79), (.25, -.78), (.30, -.72), (.30, -.68), (.35, -.65),
     (.30, -.62), (.28, -.56), (.15, -.55), (.10, -.64), (.10, -.72)),
)
ARMS = (((.13, -.38), (-.12, -.23), (.19, -.34)),
        ((.24, -.38), (.42, -.33), (.60, -.34)))
TAIL = ((-.59, .17), (-.77, .22), (-.85, .43), (-.83, .56))
BOW = ((.59, -.76), (.68, -.58), (.73, -.35), (.70, -.11), (.60, .13))
STRING = ((.59, -.74), (.20, -.34), (.60, .11))
ARROW = ((.14, -.34), (.92, -.34))
ARROWHEAD = ((.83, -.40), (.97, -.34), (.83, -.28))


def material(x, y):
    if stroke(x, y, ARROW, .013) or polygon(x, y, ARROWHEAD):
        return 2
    if (any(polygon(x, y, shape) for shape in BODY)
            or any(stroke(x, y, arm, .037) for arm in ARMS)
            or stroke(x, y, TAIL, .028) or stroke(x, y, BOW, .022)
            or stroke(x, y, STRING, .008)):
        return 1
    return 0


@lru_cache(maxsize=1)
def mesh():
    """Cache a bevelled, double-sided relief and side walls once per process."""
    materials = [material(col * STEP - EXTENT, row * STEP - EXTENT)
                 for row in range(GRID) for col in range(GRID)]
    distance = [GRID if m else 0.0 for m in materials]
    # Two chamfer passes approximate distance to the silhouette's boundary.
    for reverse in (False, True):
        indices = range(GRID * GRID - 1, -1, -1) if reverse else range(GRID * GRID)
        for i in indices:
            if not materials[i]:
                continue
            row, col = divmod(i, GRID)
            offsets = ((1, 0), (0, 1), (1, 1), (-1, 1)) if reverse else (
                (-1, 0), (0, -1), (-1, -1), (1, -1))
            for dx, dy in offsets:
                if 0 <= col + dx < GRID and 0 <= row + dy < GRID:
                    distance[i] = min(distance[i], distance[i + dy * GRID + dx]
                                      + (math.sqrt(2) if dx and dy else 1))
    result = []
    for row in range(1, GRID - 1):
        for col in range(1, GRID - 1):
            i = row * GRID + col
            if not materials[i]:
                continue
            x, y = col * STEP - EXTENT, row * STEP - EXTENT
            gx = distance[i + 1] - distance[i - 1]
            gy = distance[i + GRID] - distance[i - GRID]
            length = math.hypot(gx, gy) or 1
            edge = max(0.0, 1.0 - distance[i] * STEP / .065)
            nz = math.sqrt(1 - edge * edge)
            z = .065 + .065 * nz
            nx, ny = -gx / length * edge, -gy / length * edge
            for sign in (-1, 1):
                result.append((x, y, z * sign, nx, ny, nz * sign, materials[i] == 2))
            if distance[i] <= 1.5:
                for z in (-.06, 0, .06):
                    result.append((x, y, z, -gx / length, -gy / length, 0, materials[i] == 2))
    return tuple(result)


@dataclass(frozen=True)
class Cell:
    glyph: str
    shade: int = 0
    accent: bool = False


class Renderer:
    def frame(self, columns, rows, progress=1.0):
        if not (1 <= columns <= MAX_COLUMNS and 1 <= rows <= MAX_ROWS):
            raise ValueError('Graphic stage exceeds the bounded renderer.')
        progress = max(0.0, min(1.0, progress))
        phase = smooth(progress)
        angle = -.35 + (math.tau + .35) * phase
        tilt = math.sin(math.tau * phase) * .12
        sy, cy = math.sin(angle), math.cos(angle)
        sx, cx = math.sin(tilt), math.cos(tilt)
        dot_columns, dot_rows = columns * 2, rows * 4
        scale = min((dot_columns - 3) / 2.12, (dot_rows - 3) / 2.12)
        depth = [-math.inf] * (dot_columns * dot_rows)
        shades = [0.0] * len(depth)
        accents = [False] * len(depth)
        fade = .35 + .65 * smooth(progress / .10)
        for x, y, z, nx, ny, nz, accent in mesh():
            px, pz = x * cy + z * sy, -x * sy + z * cy
            py, pz = y * cx - pz * sx, y * sx + pz * cx
            perspective = 4.0 / (4.0 - pz)
            col = int(dot_columns / 2 + px * scale * perspective)
            row = int(dot_rows / 2 + py * scale * perspective)
            normal_x, normal_z = nx * cy + nz * sy, -nx * sy + nz * cy
            normal_y, normal_z = ny * cx - normal_z * sx, ny * sx + normal_z * cx
            diffuse = max(0, -.40 * normal_x - .52 * normal_y + .75 * normal_z)
            gloss = max(0, -.20 * normal_x - .30 * normal_y + .93 * normal_z) ** 18
            rim = (1 - abs(normal_z)) ** 2 * .18
            light = min(1.0, .20 + .63 * diffuse + .30 * gloss + rim) * fade
            # A small splat prevents holes when the relief faces sideways.
            for dx, dy in ((0, 0), (1, 0), (0, 1)):
                c, r = col + dx, row + dy
                if 0 <= c < dot_columns and 0 <= r < dot_rows:
                    i = r * dot_columns + c
                    if pz > depth[i]:
                        depth[i], shades[i], accents[i] = pz, light, accent
        result = []
        for row in range(rows):
            line = []
            for col in range(columns):
                bits, light, count, accent_count = 0, 0.0, 0, 0
                for dy, pair in enumerate(DOT_BITS):
                    for dx, bit in enumerate(pair):
                        i = (row * 4 + dy) * dot_columns + col * 2 + dx
                        if depth[i] != -math.inf:
                            bits |= bit
                            light += shades[i]
                            count += 1
                            accent_count += accents[i]
                line.append(Cell(chr(0x2800 + bits) if bits else ' ',
                                 min(15, round(light / count * 15)) if count else 0,
                                 accent_count > 0))
            result.append(tuple(line))
        return tuple(result)


class WelcomeAnimation:
    """Visible-time clock; hidden panes pause and idle poses stop rendering."""
    def __init__(self):
        self.renderer = Renderer()
        self.elapsed = 0.0
        self.previous = None
        self.cached_key = None
        self.cached_frame = None
        self.active = False

    def pause(self):
        self.previous = None
        self.active = False

    def replay(self):
        self.elapsed = 0.0
        self.previous = None
        self.cached_key = None

    def frame(self, columns, rows, now, reduced=False, editing=False):
        if reduced or editing:
            self.pause()
            if editing:
                self.elapsed = SPIN_SECONDS
            progress = 1.0
        else:
            if self.previous is not None:
                self.elapsed = min(SPIN_SECONDS, self.elapsed + max(0, now - self.previous))
            self.previous = now
            progress = self.elapsed / SPIN_SECONDS
            self.active = self.elapsed < SPIN_SECONDS
        key = (columns, rows, int(round(progress * SPIN_SECONDS / FRAME_SECONDS)))
        if key != self.cached_key:
            self.cached_frame = self.renderer.frame(columns, rows, progress)
            self.cached_key = key
        return self.cached_frame
