"""Keyboard protocols, including modified Enter and atomic bracketed paste."""

from contextlib import contextmanager
import curses
from dataclasses import dataclass
import re
import sys

KEY_NEWLINE, KEY_IGNORE, KEY_PASTE_START = 0x110000, 0x110001, 0x110002


@dataclass(frozen=True)
class PastedText:
    text: str


@contextmanager
def keyboard_protocol(stream=None):
    stream = sys.stdout if stream is None else stream
    enabled = stream.isatty()
    try:
        if enabled:
            # Kitty progressive enhancement + xterm modifyOtherKeys. Unsupported
            # controls are ignored. No all-keys or key-release mode is requested.
            stream.write('\x1b[>1u\x1b[>4;2m\x1b[?2004h')
            stream.flush()
        yield
    finally:
        if enabled:
            stream.write('\x1b[?2004l\x1b[>4m\x1b[<1u')
            stream.flush()


def decode_sequence(sequence):
    if re.fullmatch(r'(?:\[|O)[ABCDHF]', sequence):
        return {'A': curses.KEY_UP, 'B': curses.KEY_DOWN, 'C': curses.KEY_RIGHT,
                'D': curses.KEY_LEFT, 'H': curses.KEY_HOME, 'F': curses.KEY_END}[sequence[-1]]
    if sequence in ('\r', '\n'):
        return KEY_NEWLINE  # Legacy Alt+Enter / custom terminal mapping.
    if sequence == '[200~':
        return KEY_PASTE_START
    if sequence == '[201~' or re.fullmatch(r'\[\?\d+u', sequence):
        return KEY_IGNORE
    functional = re.fullmatch(r'\[1;(\d+)([ABCDHF])', sequence)
    if functional:
        modifier, key = functional.groups()
        if key == 'D' and int(modifier) == 2:
            return curses.KEY_SLEFT
        return {'A': curses.KEY_UP, 'B': curses.KEY_DOWN, 'C': curses.KEY_RIGHT,
                'D': curses.KEY_LEFT, 'H': curses.KEY_HOME, 'F': curses.KEY_END}[key]
    kitty = re.fullmatch(r'\[(\d+)(?:;(\d+)(?::([123]))?)?u', sequence)
    xterm = re.fullmatch(r'\[27;(\d+);(\d+)~', sequence)
    if kitty:
        code, modifiers, event = kitty.groups()
        if event == '3':
            return KEY_IGNORE
        code, modifiers = int(code), int(modifiers or 1)
    elif xterm:
        modifiers, code = map(int, xterm.groups())
    else:
        return None
    bits = (modifiers - 1) & 63  # Caps/num lock do not change shortcuts.
    if code == 13 and bits in (0, 1, 4, 5):
        return KEY_NEWLINE if bits & 1 else '\r'
    if bits & 4 and not bits & ~5 and 64 <= code <= 127:
        return chr(code & 31)
    if bits in (0, 1) and code in (9, 27, 127):
        return {9: '\t', 27: '\x1b', 127: '\x7f'}[code]
    if bits in (0, 1) and 32 <= code <= 0x10ffff:
        return chr(code)
    return KEY_IGNORE


def read_key(screen, timeout=100):
    key = screen.get_wch()
    if key != '\x1b':
        return key
    consumed = []
    screen.timeout(25)
    try:
        for _ in range(64):
            try:
                character = screen.get_wch()
            except curses.error:
                break
            consumed.append(character)
            if not isinstance(character, str):
                break
            if len(consumed) == 1:
                if character not in ('[', 'O'):
                    break
            elif '@' <= character <= '~':
                break
        sequence = ''.join(character for character in consumed if isinstance(character, str))
        decoded = decode_sequence(sequence)
        if decoded is not None:
            return decoded
    finally:
        screen.timeout(timeout)
    # Unknown escapes retain their keystrokes; standalone Escape remains Escape.
    for character in reversed(consumed):
        if isinstance(character, str):
            curses.unget_wch(character)
        else:
            curses.ungetch(character)
    return key


class KeyboardReader:
    def __init__(self):
        self.paste = None

    def read(self, screen, timeout=100):
        if self.paste is None:
            key = read_key(screen, timeout)
            if key != KEY_PASTE_START:
                return key
            self.paste = []
        screen.timeout(25)
        try:
            # Bounded chunks keep redraw, Ctrl+C and resize responsive during paste.
            for _ in range(4096):
                try:
                    character = screen.get_wch()
                except curses.error:
                    return KEY_IGNORE
                if character == '\x03':
                    self.paste = None
                    return character
                if not isinstance(character, str):
                    if character == curses.KEY_RESIZE:
                        return character
                    continue
                self.paste.append(character)
                if ''.join(self.paste[-6:]) == '\x1b[201~':
                    text = ''.join(self.paste[:-6]).replace('\r\n', '\n').replace('\r', '\n')
                    self.paste = None
                    text = ''.join(char for char in text if char.isprintable() or char in '\n\t')
                    return PastedText(text.replace('\t', '    '))
            return KEY_IGNORE
        finally:
            screen.timeout(timeout)
