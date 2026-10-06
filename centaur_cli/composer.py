"""Layout de entrada: quebra visual sem alterar o texto da mensagem."""

from dataclasses import dataclass

from .appearance import cell_width


@dataclass
class InputLayout:
    lines: list
    positions: list

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
