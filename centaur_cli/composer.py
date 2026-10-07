"""Layout de entrada: quebra visual sem alterar o texto da mensagem."""

from dataclasses import dataclass

from .appearance import cell_width


@dataclass
class InputLayout:
    lines: list
    positions: list

    def at(self, row, column):
        """Nearest insertion point in terminal cells, including wide glyphs."""
        row = min(max(0, row), len(self.lines) - 1)
        candidates = [(index, col) for index, (line, col) in enumerate(self.positions) if line == row]
        if not candidates:
            return len(self.positions) - 1
        last, last_column = candidates[-1]
        if column >= cell_width(self.lines[row]) and last_column < cell_width(self.lines[row]):
            return last + 1  # A wrapped boundary belongs to the next visual row.
        return min(candidates, key=lambda item: (abs(item[1] - max(0, column)), item[1], -item[0]))[0]

    def vertical(self, cursor, direction, column=None):
        row, current_column = self.positions[cursor]
        column = current_column if column is None else column
        target = min(len(self.lines) - 1, max(0, row + direction))
        candidates = [(index, col) for index, (line, col) in enumerate(self.positions) if line == target]
        if not candidates:
            return cursor, column
        before = [(index, col) for index, col in candidates if col <= column]
        return (max(before, key=lambda item: (item[1], item[0]))[0] if before else candidates[0][0]), column


def layout_input(text, width):
    width = max(1, width)
    lines, positions, fragment = [], [(0, 0)], []
    row, column = 0, 0
    for character in text:
        if character == '\n':
            lines.append(''.join(fragment))
            fragment = []
            row, column = row + 1, 0
        else:
            cells = cell_width(character)
            if column + cells > width and fragment:
                lines.append(''.join(fragment))
                fragment = []
                row, column = row + 1, 0
                positions[-1] = (row, 0)
            fragment.append(character)
            column += cells
        positions.append((row, column))
    lines.append(''.join(fragment))
    # An insertion point at the right edge belongs to the next visual row.
    if column >= width:
        lines.append('')
        positions[-1] = (row + 1, 0)
    return InputLayout(lines, positions)


def attachment_span(item, text):
    span = item.get('span')
    if (isinstance(span, (list, tuple)) and len(span) == 2
            and all(type(position) is int for position in span)
            and 0 <= span[0] < span[1] <= len(text)
            and text[span[0]:span[1]] == item.get('marker')):
        return span
    return None


def atomic_cursor(text, items, cursor, direction=1):
    for item in items:
        span = attachment_span(item, text)
        if span and span[0] < cursor < span[1]:
            return span[1] if direction > 0 else span[0]
    return cursor


def replace_input(text, items, start, end, replacement):
    """Attachment placeholders behave as indivisible editor elements."""
    start, end = max(0, start), min(len(text), end)
    for item in items:
        span = attachment_span(item, text)
        if span and start != end and start < span[1] and end > span[0]:
            start, end = min(start, span[0]), max(end, span[1])
        elif span and start == end and span[0] < start < span[1]:
            start = end = span[1]
    delta = len(replacement) - (end - start)
    kept = []
    for item in items:
        span = attachment_span(item, text)
        if span and start < span[1] and end > span[0]:
            continue
        if span and span[0] >= end:
            item['span'] = [span[0] + delta, span[1] + delta]
        kept.append(item)
    items[:] = kept
    return text[:start] + replacement + text[end:], start + len(replacement)


def without_attachment_markers(text, items):
    spans = sorted([span for item in items if (span := attachment_span(item, text))], reverse=True)
    for start, end in spans:
        text = text[:start] + text[end:]
    return text
