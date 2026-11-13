"""Small CPU renderer: convergence ribbons, lighting, depth and Unicode Braille.

No terminal I/O or dependencies live here. One cached mesh is projected into a
bounded 2 × 4 dot grid; the view owns colors and writes the resulting cells.
"""

from dataclasses import dataclass
from functools import lru_cache
import math

FRAME_SECONDS = 1 / 30
SPIN_SECONDS = 4.8
# The mark is drawn from the tails to the shared tip while the turn is still slow,
# and a highlight crosses it as the turn settles into the front pose.
REVEAL_SECONDS = 1.1
GLINT_START = .8
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


def ribbon(mirrored=False):
    """Two slim cubic bands meet at a single tip; width tapers at the junction."""
    control = ((-.80, -.67), (-.06, -.72), (.18, -.23), (.90, 0.0))
    left, right = [], []
    for step in range(49):
        t, u = step / 48, 1 - step / 48
        x, y = (sum(weight * point[axis] for weight, point in zip(
            (u ** 3, 3 * u * u * t, 3 * u * t * t, t ** 3), control)) for axis in (0, 1))
        dx, dy = (3 * sum(weight * (b[axis] - a[axis]) for weight, a, b in zip(
            (u * u, 2 * u * t, t * t), control, control[1:])) for axis in (0, 1))
        length = math.hypot(dx, dy)
        # Full band width is about .13 world units, with a pointed shared tip.
        width = (.065 + .008 * math.sin(math.pi * t)) * (1 - smooth((t - .78) / .22))
        nx, ny = -dy / length * width, dx / length * width
        sign = -1 if mirrored else 1
        left.append((x + nx, (y + ny) * sign))
        right.append((x - nx, (y - ny) * sign))
    return tuple(left + list(reversed(right)))


# Human judgment (silver) and AI execution (green), converging on one direction.
UPPER_RIBBON = ribbon()
LOWER_RIBBON = ribbon(mirrored=True)
ARROWHEAD = ((.82, -.075), (1.01, 0.0), (.82, .075))


def material(x, y):
    # A slender green arrow crosses the negative space and projects past the tip.
    if (-.72 <= x <= .88 and abs(y) <= .013) or polygon(x, y, ARROWHEAD):
        return 2
    if polygon(x, y, LOWER_RIBBON):
        return 2
    if polygon(x, y, UPPER_RIBBON):
        return 1
    return 0


@lru_cache(maxsize=4)
def flat_symbol(columns, rows, ascii_only=False):
    """Static block/ASCII fallback derived from the same vector mark."""
    scale = min((columns * 2 - 3) / 2.12, (rows * 4 - 3) / 2.12)
    lines = []
    for row in range(rows):
        line = []
        for col in range(columns):
            top, bottom = False, False
            for dy in range(4):
                for dx in range(2):
                    x = (col * 2 + dx - columns) / scale
                    y = (row * 4 + dy - rows * 2) / scale
                    if material(x, y):
                        if dy < 2:
                            top = True
                        else:
                            bottom = True
            line.append('#' if ascii_only and (top or bottom) else ' ' if ascii_only else
                        '█' if top and bottom else '▀' if top else '▄' if bottom else ' ')
        lines.append(''.join(line))
    return tuple(lines)


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
    def frame(self, columns, rows, progress=1.0, reveal=1.0, glint=None):
        """reveal draws the mark from left to right; glint is the position of a passing highlight."""
        if not (1 <= columns <= MAX_COLUMNS and 1 <= rows <= MAX_ROWS):
            raise ValueError('Graphic stage exceeds the bounded renderer.')
        progress = max(0.0, min(1.0, progress))
        phase = smooth(progress)
        angle = math.tau * phase if progress < 1 else 0.0
        tilt = math.sin(math.tau * phase) * .08 if progress < 1 else 0.0
        sy, cy = math.sin(angle), math.cos(angle)
        sx, cx = math.sin(tilt), math.cos(tilt)
        dot_columns, dot_rows = columns * 2, rows * 4
        scale = min((dot_columns - 3) / 2.12, (dot_rows - 3) / 2.12)
        # Foreshortened surfaces cover fewer dots; retain their side walls.
        coverage_threshold = min(.28, (STEP * scale) ** 2) * (.35 + .65 * abs(cy))
        depth_tolerance = STEP * 2 + abs(sy) / max(1.0, scale)
        depth = [-math.inf] * (dot_columns * dot_rows)
        shades = [0.0] * len(depth)
        coverage = [0.0] * len(depth)
        accents = [False] * len(depth)
        fade = .55 + .45 * smooth(progress / .12)
        front = math.inf if reveal >= 1 else -EXTENT + max(0.0, reveal) * EXTENT * 2.1
        half_columns, half_rows = dot_columns / 2 - .5, dot_rows / 2 - .5
        step_scale = STEP * scale
        for x, y, z, nx, ny, nz, accent in mesh():
            if x > front:
                continue
            normal_x, normal_z = nx * cy + nz * sy, -nx * sy + nz * cy
            normal_y, normal_z = ny * cx - normal_z * sx, ny * sx + normal_z * cx
            # The relief is a thin double-sided sheet: faces turned away are hidden by the
            # near side, so skip them before projecting. Side walls (normal_z near 0) stay.
            if normal_z < -.25:
                continue
            px, pz = x * cy + z * sy, -x * sy + z * cy
            py, pz = y * cx - pz * sx, y * sx + pz * cx
            perspective = 4.0 / (4.0 - pz)
            projected_x = half_columns + px * scale * perspective
            projected_y = half_rows + py * scale * perspective
            col, row = math.floor(projected_x), math.floor(projected_y)
            if not (-1 <= col < dot_columns and -1 <= row < dot_rows):
                continue
            fraction_x, fraction_y = projected_x - col, projected_y - row
            diffuse = -.40 * normal_x - .52 * normal_y + .75 * normal_z
            gloss = -.20 * normal_x - .30 * normal_y + .93 * normal_z
            light = .20 + (.63 * diffuse if diffuse > 0 else 0) + (.30 * gloss ** 18 if gloss > 0 else 0) \
                + (1 - abs(normal_z)) ** 2 * .18
            light = (light if light < 1 else 1.0) * fade
            if front - x < .12:
                light = min(1.0, light + .6 * (1 - (front - x) / .12))  # The bright point that draws the line.
            if glint is not None:
                light = min(1.0, light + .6 * max(0.0, 1 - abs(x + .45 * y - glint) / .22))
            # Distribute surface coverage across neighboring dots instead of
            # inflating every sample into an opaque L-shaped splat.
            area = step_scale * perspective
            area = area * area if area < 1 else 1.0
            i = row * dot_columns + col
            for c, r, i, weight in ((col, row, i, (1 - fraction_x) * (1 - fraction_y)),
                                    (col + 1, row, i + 1, fraction_x * (1 - fraction_y)),
                                    (col, row + 1, i + dot_columns, (1 - fraction_x) * fraction_y),
                                    (col + 1, row + 1, i + dot_columns + 1, fraction_x * fraction_y)):
                if weight and 0 <= c < dot_columns and 0 <= r < dot_rows:
                    known = depth[i]
                    if pz > known + depth_tolerance:
                        depth[i], shades[i], accents[i] = pz, light, accent
                        coverage[i] = area * weight
                    elif pz - known >= -depth_tolerance:
                        coverage[i] += area * weight
                        if pz > known:
                            depth[i], shades[i], accents[i] = pz, light, accent
        result = []
        for row in range(rows):
            line = []
            for col in range(columns):
                bits, light, count, accent_count = 0, 0.0, 0, 0
                for dy, pair in enumerate(DOT_BITS):
                    for dx, bit in enumerate(pair):
                        i = (row * 4 + dy) * dot_columns + col * 2 + dx
                        if coverage[i] >= coverage_threshold:
                            bits |= bit
                            light += shades[i]
                            count += 1
                            accent_count += accents[i]
                line.append(Cell(chr(0x2800 + bits) if bits else ' ',
                                 min(15, round(light / count * 15)) if count else 0,
                                 accent_count * 2 >= count if count else False))
            result.append(tuple(line))
        return tuple(result)


class WelcomeAnimation:
    """Visible-time clock; hidden panes pause and idle poses stop rendering."""
    opening_played = False  # Set by the startup screen once the user has watched the opening there.

    def __init__(self):
        self.renderer = Renderer()
        self.elapsed = SPIN_SECONDS if WelcomeAnimation.opening_played else 0.0
        self.previous = None
        self.cached_key = None
        self.cached_frame = None
        self.active = False

    def pause(self):
        self.previous = None
        self.active = False

    def settle(self):
        """Skip to the final pose, e.g. when the opening already played on the previous screen."""
        self.elapsed = SPIN_SECONDS
        self.pause()

    def staged(self, start, duration=0.0):
        """0..1 progress of an accompanying element; 1 whenever the mark is not moving."""
        if not self.active:
            return 1.0
        return 1.0 if duration <= 0 and self.elapsed >= start else 0.0 if duration <= 0 else smooth((self.elapsed - start) / duration)

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
            sampled_progress = min(1.0, key[2] * FRAME_SECONDS / SPIN_SECONDS)
            moving = sampled_progress < 1
            reveal = smooth(sampled_progress * SPIN_SECONDS / REVEAL_SECONDS) if moving else 1.0
            glint = (-1.5 + 3.0 * (sampled_progress - GLINT_START) / (1 - GLINT_START)
                     if moving and sampled_progress >= GLINT_START else None)
            self.cached_frame = self.renderer.frame(columns, rows, sampled_progress, reveal=reveal, glint=glint)
            self.cached_key = key
        return self.cached_frame
