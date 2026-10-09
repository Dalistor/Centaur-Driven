"""Keyboard protocols, including modified Enter and atomic bracketed paste."""

from contextlib import contextmanager
import curses
from dataclasses import dataclass
import re
import sys
import time

KEY_NEWLINE, KEY_IGNORE, KEY_PASTE_START = 0x110000, 0x110001, 0x110002
KEY_FOCUS_IN, KEY_FOCUS_OUT = 0x110003, 0x110004


@dataclass(frozen=True)
class PastedText:
    text: str


@contextmanager
def keyboard_protocol(stream=None, *, plain=False):
    stream = sys.stdout if stream is None else stream
    enabled = stream.isatty()
    try:
        if enabled:
            # All keys + associated text make Shift+Space distinguishable while
            # retaining the actual typed text. Release reporting is not requested.
            stream.write('\x1b[>0u\x1b[>4m\x1b[?2004l\x1b[?1004l' if plain else
                         '\x1b[>25u\x1b[>4;2m\x1b[?2004h\x1b[?1004h')
            stream.flush()
        yield
    finally:
        if enabled:
            stream.write('\x1b[<1u\x1b[>4;2m\x1b[?2004h\x1b[?1004h' if plain else
                         '\x1b[?1004l\x1b[?2004l\x1b[>4m\x1b[<1u')
            stream.flush()


def decode_sequence(sequence):
    if sequence in ('[I', '[O'):
        return KEY_FOCUS_IN if sequence == '[I' else KEY_FOCUS_OUT
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
    kitty = re.fullmatch(r'\[(\d+)(?::\d*(?::\d*)?)?(?:;(\d*)(?::([123]))?)?(?:;(\d+(?::\d+)*))?u', sequence)
    xterm = re.fullmatch(r'\[27;(\d+);(\d+)~', sequence)
    if kitty:
        code, modifiers, event, text = kitty.groups()
        if event == '3':
            return KEY_IGNORE
        code, modifiers = int(code), int(modifiers or 1)
    elif xterm:
        modifiers, code = map(int, xterm.groups())
    else:
        return None
    bits = (modifiers - 1) & 63  # Caps/num lock do not change shortcuts.
    if code == 32 and bits == 1:
        return KEY_NEWLINE
    if code == 57414:
        code = 13  # Kitty keypad Enter.
    if code == 13 and bits in (0, 1, 4, 5):
        if kitty and event == '2' and not bits & 1:
            return KEY_IGNORE  # An explicit repeat must never submit a draft.
        return KEY_NEWLINE if bits & 1 else '\r'
    if bits & 4 and not bits & ~5 and 64 <= code <= 127:
        return chr(code & 31)
    if bits in (0, 1) and code in (9, 27, 127):
        return {9: '\t', 27: '\x1b', 127: '\x7f'}[code]
    keypad_navigation = {57417: curses.KEY_LEFT, 57418: curses.KEY_RIGHT,
                         57419: curses.KEY_UP, 57420: curses.KEY_DOWN,
                         57421: curses.KEY_PPAGE, 57422: curses.KEY_NPAGE,
                         57423: curses.KEY_HOME, 57424: curses.KEY_END,
                         57425: curses.KEY_IC, 57426: curses.KEY_DC}
    if code in keypad_navigation:
        return curses.KEY_SLEFT if code == 57417 and bits == 1 else keypad_navigation[code]
    if kitty and text:
        points = [int(point) for point in text.split(':')]
        if all(32 <= point <= 0x10ffff and not 127 <= point <= 159
               and not 0xd800 <= point <= 0xdfff for point in points):
            return ''.join(chr(point) for point in points)
        return KEY_IGNORE
    if 57344 <= code <= 63743:
        return KEY_IGNORE  # Modifier/media keys are not characters in the draft.
    if bits in (0, 1) and 32 <= code <= 0x10ffff:
        return chr(code)
    return KEY_IGNORE


def read_key(screen, timeout=100):
    """One-shot compatibility helper; streaming input must retain KeyboardReader."""
    return KeyboardReader()._read_key(screen, timeout, one_shot=True)


class KeyboardReader:
    def __init__(self):
        self.paste = None
        self.escape = None
        self.escape_deadline = 0

    def _finish_escape(self):
        sequence, self.escape = self.escape, None
        if not sequence:
            return '\x1b'
        decoded = decode_sequence(sequence)
        # Never replay an incomplete/unsupported protocol frame into the composer.
        return KEY_IGNORE if decoded is None else decoded

    def _read_key(self, screen, timeout, one_shot=False):
        if self.escape is None:
            key = screen.get_wch()
            if isinstance(key, int):
                # Extended focus key numbers depend on the terminal's terminfo.
                try:
                    name = curses.keyname(key)
                except curses.error:
                    name = None
                if name in (b'kxIN', b'kxOUT'):
                    return KEY_FOCUS_IN if name == b'kxIN' else KEY_FOCUS_OUT
            if key != '\x1b':
                return key
            self.escape = ''
            self.escape_deadline = time.monotonic() + .25
        screen.timeout(25)
        try:
            for _ in range(64):
                try:
                    character = screen.get_wch()
                except curses.error:
                    if one_shot or time.monotonic() >= self.escape_deadline:
                        return self._finish_escape()
                    return KEY_IGNORE  # Continue the same frame on the next read.
                if character == '\x03':
                    self.escape = None
                    return character
                if isinstance(character, int):
                    return character  # Resize stays responsive without losing fragments.
                if not self.escape and character not in ('[', 'O'):
                    self.escape = None
                    if character in ('\r', '\n'):
                        return KEY_NEWLINE
                    curses.unget_wch(character)
                    return '\x1b'
                if not character.isprintable():
                    self.escape = None
                    return KEY_IGNORE  # A damaged frame cannot turn CR into submit.
                self.escape += character
                if len(self.escape) > 1 and '@' <= character <= '~':
                    return self._finish_escape()
                if len(self.escape) >= 64:
                    self.escape = None
                    return KEY_IGNORE
            return KEY_IGNORE
        finally:
            screen.timeout(timeout)

    def read(self, screen, timeout=100):
        if self.paste is None:
            key = self._read_key(screen, timeout)
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
