"""Markdown da conversa desenhado para o terminal: títulos, listas, tabelas, código e ênfase.

Cada linha devolvida é texto puro (o que a seleção do emulador copia) com trechos
estilizados à parte, para a tela pintar negrito, código e bordas sem marcadores.
"""

import functools
import re

from .appearance import cell_width
from .conversation import TranscriptLine

INLINE = re.compile(
    r'(`+)(.+?)\1'                                             # código
    r'|\*\*(?=\S)(.+?)(?<=\S)\*\*|__(?=\S)(.+?)(?<=\S)__'      # negrito
    r'|~~(?=\S)(.+?)(?<=\S)~~'                                 # riscado: só remove os marcadores
    r'|\[([^\]\n]+)\]\(([^)\s]+)\)'                            # link
    r'|(?<![\w*])\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?![\w*])'      # itálico
    r'|(?<!\w)_(?=[^\s_])(.+?)(?<=[^\s_])_(?!\w)')
ESCAPED = re.compile(r'\\([\\`*_{}\[\]()#+\-.!|~>])')
FENCE = re.compile(r'^\s*(```+|~~~+)\s*([\w+#.-]*)')
HEADING = re.compile(r'^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$')
RULE = re.compile(r'^\s{0,3}([-*_])(?:\s*\1){2,}\s*$')
QUOTE = re.compile(r'^\s{0,3}>\s?(.*)$')
ITEM = re.compile(r'^(\s*)([-*+]|\d{1,4}[.)])\s+(.*)$')
TASK = re.compile(r'^\[([ xX])\]\s+(.*)$')
DIVIDER = re.compile(r'^\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?\s*$')
PRIVATE = 0xE000  # Caracteres escapados ficam fora do alcance dos marcadores até o fim.
MAX_INDENT = 16


def protect(text):
    return ESCAPED.sub(lambda match: chr(PRIVATE + ord(match.group(1))), text)


def restore(text):
    return ''.join(chr(ord(char) - PRIVATE) if PRIVATE < ord(char) < PRIVATE + 128 else char for char in text)


def inline(text, style=None):
    """Lista de (texto, estilo) sem os marcadores de ênfase."""
    parts, position = [], 0
    for match in INLINE.finditer(text):
        if match.start() > position:
            parts.append((text[position:match.start()], style))
        ticks, code, bold, bold_alt, struck, label, target, italic, italic_alt = match.groups()
        if ticks:
            parts.append((code.strip() if code.strip() else code, 'code'))
        elif bold is not None or bold_alt is not None:
            parts += inline(bold or bold_alt, 'strong')
        elif struck is not None:
            parts += inline(struck, style)
        elif label is not None:
            parts += inline(label, 'link')
            if target != label and not target.startswith('#'):
                parts.append((f' ({target})', 'muted'))
        else:
            parts += inline(italic or italic_alt, style if style == 'strong' else 'emphasis')
        position = match.end()
    if position < len(text):
        parts.append((text[position:], style))
    return [(restore(piece), mark) for piece, mark in parts if piece]


def cells(text, style=None):
    """Uma entrada por caractere: (caractere, estilo)."""
    return [(char, mark) for piece, mark in inline(protect(text), style) for char in piece]


def plain(text):
    return ''.join(char for char, _ in cells(text))


def wrap(content, width):
    """Quebra por palavras em linhas de até `width` células, preservando o estilo de cada caractere."""
    width = max(1, width)
    lines, line, used = [], [], 0
    word, word_width = [], 0

    def flush_word():
        nonlocal line, used, word, word_width
        if not word:
            return
        gap = 1 if line else 0
        if used + gap + word_width > width and line:
            lines.append(line)
            line, used, gap = [], 0, 0
        while word_width > width:  # Palavra maior que a linha: corta por células.
            taken, taken_width = [], 0
            while word and taken_width + cell_width(word[0][0]) <= width:
                taken_width += cell_width(word[0][0])
                taken.append(word.pop(0))
            if not taken:
                taken, taken_width = [word.pop(0)], width
            lines.append(taken)
            word_width = sum(cell_width(char) for char, _ in word)
        if word:
            if gap:
                line.append((' ', None if line[-1][1] != word[0][1] else line[-1][1]))
            line += word
            used += gap + word_width
        word, word_width = [], 0

    for char, mark in content:
        if char.isspace():
            flush_word()
        else:
            word.append((char, mark))
            word_width += cell_width(char)
    flush_word()
    if line or not lines:
        lines.append(line)
    return lines


def build(prefix, content, style, prefix_style=None):
    """Monta a linha de tela: texto puro e os trechos cujo estilo difere do estilo-base."""
    text = prefix + ''.join(char for char, _ in content)
    spans, start, current = [], len(prefix), None
    if prefix_style and prefix.strip():
        spans.append((0, len(prefix), prefix_style))
    for index, (_, mark) in enumerate(content, len(prefix)):
        if mark != current:
            if current:
                spans.append((start, index, current))
            start, current = index, mark
    if current:
        spans.append((start, len(text), current))
    return TranscriptLine(text, style, tuple(spans))


def paragraph(text, width, style, first='', rest=None, prefix_style=None, mark=None):
    rest = first if rest is None else rest
    wrapped = wrap(cells(text, mark), width - cell_width(first))
    return [build(first if index == 0 else rest, line, style, prefix_style if index == 0 else None)
            for index, line in enumerate(wrapped)]


def split_row(line):
    """Células de uma linha de tabela; `|` escapado ou dentro de código não separa."""
    line = protect(line.strip())
    row, current, ticks = [], [], False
    for char in line:
        if char == '`':
            ticks = not ticks
        if char == '|' and not ticks:
            row.append(''.join(current).strip())
            current = []
        else:
            current.append(char)
    row.append(''.join(current).strip())
    if line.startswith('|'):
        row = row[1:]
    if line.endswith('|') and row:
        row = row[:-1]
    return [restore_escapes(cell) for cell in row]


def restore_escapes(text):
    # Devolve o escape para a análise de ênfase tratá-lo; só o separador já foi resolvido.
    return ''.join('\\' + chr(ord(char) - PRIVATE) if PRIVATE < ord(char) < PRIVATE + 128 else char for char in text)


def column_widths(natural, available):
    """Reparte a largura: colunas curtas ficam inteiras, as longas dividem o que sobra."""
    widths, pending, room = [0] * len(natural), list(range(len(natural))), available
    while pending:
        share = max(1, room // len(pending))
        small = [index for index in pending if natural[index] <= share]
        if not small:
            for position, index in enumerate(pending):
                widths[index] = share + (1 if position < room - share * len(pending) else 0)
            break
        for index in small:
            widths[index] = natural[index]
            room -= natural[index]
            pending.remove(index)
    return widths


def table(rows, alignments, width, style, indent):
    count = max(len(row) for row in rows)
    rows = [row + [''] * (count - len(row)) for row in rows]
    alignments = (alignments + ['left'] * count)[:count]
    available = width - cell_width(indent) - (3 * count + 1)
    if available < count * 4:
        return stacked(rows, width, style, indent)
    natural = [max(1, max(cell_width(plain(row[column])) for row in rows)) for column in range(count)]
    widths = column_widths(natural, available) if sum(natural) > available else natural
    rendered = [[wrap(cells(cell, 'strong' if number == 0 else None), widths[column]) for column, cell in enumerate(row)]
                for number, row in enumerate(rows)]
    tall = any(len(cell) > 1 for row in rendered[1:] for cell in row)

    def border(left, middle, right):
        return TranscriptLine(indent + left + middle.join('─' * (size + 2) for size in widths) + right, 'line')

    lines = [border('┌', '┬', '┐')]
    for number, row in enumerate(rendered):
        if number == 1 or (number > 1 and tall):
            lines.append(border('├', '┼', '┤'))
        for level in range(max(len(cell) for cell in row)):
            content = [('│', 'line')]
            for column, cell in enumerate(row):
                piece = cell[level] if level < len(cell) else []
                free = widths[column] - sum(cell_width(char) for char, _ in piece)
                left = free if alignments[column] == 'right' else free // 2 if alignments[column] == 'center' else 0
                content += [(' ', None)] * (1 + left) + piece + [(' ', None)] * (1 + free - left) + [('│', 'line')]
            lines.append(build(indent, content, style))
    lines.append(border('└', '┴', '┘'))
    return lines


def stacked(rows, width, style, indent):
    """Tela estreita demais para colunas: cada linha vira um bloco "Cabeçalho: valor"."""
    lines = []
    for row in rows[1:]:
        for header, cell in zip(rows[0], row):
            if cell:
                label = plain(header)
                lines += paragraph(f'**{label}:** {cell}' if label else cell, width, style, indent, indent + '  ')
        lines.append(TranscriptLine(''))
    return lines[:-1]


def alignment(cell):
    cell = cell.strip()
    return 'center' if cell.startswith(':') and cell.endswith(':') else 'right' if cell.endswith(':') else 'left'


@functools.lru_cache(maxsize=512)
def render(text, width, style='text', indent=''):
    """Linhas de tela (TranscriptLine) para um texto em Markdown."""
    width = max(8, width)
    source = ''.join(char if char.isprintable() or char == '\n' else ' ' for char in str(text).replace('\t', '    ')).split('\n')
    lines, index = [], 0
    while index < len(source):
        line = source[index]
        fence = FENCE.match(line)
        if fence:
            marker, language = fence.group(1)[:3], fence.group(2)
            if language:
                lines.append(TranscriptLine(indent + '  ' + language, 'muted'))
            index += 1
            while index < len(source) and not source[index].strip().startswith(marker):
                code = source[index]
                room = max(1, width - cell_width(indent) - 2)
                while True:  # Código não é reorganizado: só cortado na largura da tela.
                    piece, used = '', 0
                    for char in code:
                        if used + cell_width(char) > room:
                            break
                        piece, used = piece + char, used + cell_width(char)
                    lines.append(TranscriptLine(indent + '  ' + piece, 'code'))
                    code = code[len(piece):]
                    if not code or not piece:
                        break
                index += 1
            index += 1
            continue
        if '|' in line and index + 1 < len(source) and '|' in source[index + 1] and DIVIDER.match(source[index + 1]):
            rows, alignments = [split_row(line)], [alignment(cell) for cell in split_row(source[index + 1])]
            index += 2
            while index < len(source) and '|' in source[index] and source[index].strip():
                rows.append(split_row(source[index]))
                index += 1
            lines += table(rows, alignments, width, style, indent)
            continue
        index += 1
        if not line.strip():
            lines.append(TranscriptLine(indent.rstrip(), style) if indent.strip() else TranscriptLine(''))
            continue
        heading = HEADING.match(line)
        if heading:
            lines += paragraph(heading.group(2), width, style, indent, mark='heading' if len(heading.group(1)) <= 2 else 'strong')
            continue
        if RULE.match(line):
            lines.append(TranscriptLine(indent + '─' * min(48, width - cell_width(indent)), 'line'))
            continue
        quote = QUOTE.match(line)
        if quote:
            lines += paragraph(quote.group(1), width, style, indent + '▎ ', prefix_style='line', mark='emphasis')
            continue
        item = ITEM.match(line)
        if item:
            lead = indent + ' ' * min(MAX_INDENT, len(item.group(1)))
            bullet, body = item.group(2), item.group(3)
            task = TASK.match(body)
            if task:
                bullet, body = '☑' if task.group(1).strip() else '☐', task.group(2)
            elif not bullet[0].isdigit():
                bullet = '•'
            lines += paragraph(body, width, style, f'{lead}{bullet} ', lead + ' ' * (cell_width(bullet) + 1), prefix_style='muted')
            continue
        lead = indent + ' ' * min(MAX_INDENT, len(line) - len(line.lstrip()))
        lines += paragraph(line.strip(), width, style, lead)
    return tuple(lines)
