"""Read-only, user-invoked clipboard access with bounded native commands."""

import io
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlparse

from .attachments import MAX_FILE, MAX_TEXT


def pasted_paths(root, text):
    """Only a complete list of existing local files is an attachment paste."""
    if not text.strip() or '\x00' in text:
        return None
    lines = [line for line in text.strip().splitlines() if line and not line.startswith('#')]
    uri_list = bool(lines) and all(line.startswith('file:') for line in lines)
    try:
        tokens = lines if uri_list else shlex.split(text)
        # An unquoted clipboard path can contain spaces. This is only a probe:
        # normal prose can exceed filesystem limits or contain invalid path syntax.
        if not uri_list:
            whole = Path(text.strip()).expanduser()
            whole = whole if whole.is_absolute() else Path(root) / whole
            if whole.is_file():
                tokens = [text.strip()]
        paths = []
        for token in tokens:
            if token.startswith('file:'):
                uri = urlparse(token)
                if uri.netloc not in ('', 'localhost') or uri.query or uri.fragment:
                    return None
                token = unquote(uri.path)
            path = Path(token).expanduser()
            path = path if path.is_absolute() else Path(root) / path
            if not path.is_file():
                return None
            paths.append(str(path))
        return paths or None
    except (OSError, ValueError, RuntimeError):
        # Failed stat/URL parsing/home expansion means this paste is literal text,
        # not a confirmed file list. Never discard the paste or abort the terminal.
        return None


def read_command(arguments, limit, *, cancellation=None):
    """Spool output to private disk: oversized clipboards never fill RAM."""
    executable = shutil.which(arguments[0])
    if not executable:
        raise RuntimeError('Leitor de clipboard não instalado: ' + arguments[0])
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        process = subprocess.Popen([executable, *arguments[1:]], stdin=subprocess.DEVNULL,
                                   stdout=output, stderr=errors)
        try:
            import time
            deadline = time.monotonic() + 4
            while process.poll() is None:
                if cancellation and cancellation.wait(.03):
                    raise RuntimeError('Colagem cancelada.')
                if not cancellation:
                    time.sleep(.03)
                if output.tell() > limit or os.fstat(output.fileno()).st_size > limit:
                    raise ValueError('Clipboard excede o limite do anexo ou texto.')
                if time.monotonic() >= deadline:
                    raise RuntimeError('Clipboard não respondeu em quatro segundos.')
            if process.returncode:
                raise RuntimeError('Não foi possível ler este formato do clipboard.')
            output.seek(0)
            data = output.read(limit + 1)
            if len(data) > limit:
                raise ValueError('Clipboard excede o limite do anexo ou texto.')
            return data
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()


def mac_file_urls(cancellation=None):
    # Read AppKit's file URL items directly; pbpaste loses Finder file identity.
    # Keep an explicit return and legacy-compatible bindings in JXA's
    # automation context instead of relying on top-level completion values.
    script = ('ObjC.import("AppKit"); function run() { '
              'var pasteboard = $.NSPasteboard.generalPasteboard; '
              'var items = pasteboard.pasteboardItems; '
              'var urls = []; if (items) { for (var i = 0; i < items.count; i++) { '
              'var value = ObjC.unwrap(items.objectAtIndex(i).stringForType($("public.file-url"))); '
              'if (typeof value === "string" && value.indexOf("file:") === 0) urls.push(value); '
              '} } if (!urls.length) { '
              'var value = ObjC.unwrap(pasteboard.stringForType($("public.file-url"))); '
              'if (typeof value === "string" && value.indexOf("file:") === 0) urls.push(value); '
              '} return urls.join("\\n"); }')
    return read_command(['osascript', '-l', 'JavaScript', '-e', script], MAX_TEXT,
                        cancellation=cancellation).decode('utf-8').rstrip('\r\n')


def clipboard_content(*, cancellation=None):
    if sys.platform == 'darwin':
        try:
            files = mac_file_urls(cancellation)
        except RuntimeError:
            files = ''
        if files:
            return 'text', files
        try:
            from PIL import ImageGrab, Image
        except ImportError:
            return 'text', read_command(['pbpaste'], MAX_TEXT, cancellation=cancellation).decode('utf-8')
        value = ImageGrab.grabclipboard()
        if isinstance(value, Image.Image):
            if value.width * value.height > 25_000_000:
                raise ValueError('Imagem de clipboard excede 25 megapixels.')
            output = io.BytesIO()
            value.save(output, format='PNG')
            return 'image', output.getvalue()
        if isinstance(value, list) and value:
            return 'text', '\n'.join(Path(path).absolute().as_uri() for path in value)
        return 'text', read_command(['pbpaste'], MAX_TEXT, cancellation=cancellation).decode('utf-8')
    if sys.platform.startswith('linux'):
        wayland = bool(os.environ.get('WAYLAND_DISPLAY'))
        command = 'wl-paste' if wayland else 'xclip'
        args = ['wl-paste', '--list-types'] if wayland else ['xclip', '-selection', 'clipboard', '-t', 'TARGETS', '-o']
        try:
            types = read_command(args, 16384, cancellation=cancellation).decode('utf-8', errors='replace').splitlines()
        except RuntimeError:
            raise RuntimeError('Clipboard indisponível: instale wl-clipboard no Wayland ou xclip no X11. No SSH, cole o caminho de uma imagem salva na máquina do Centaur.') from None
        chosen = next((kind for kind in ('text/uri-list','image/png','image/jpeg','image/webp','UTF8_STRING','text/plain;charset=utf-8','text/plain','STRING') if kind in types), None)
        if not chosen:
            return 'text', ''
        args = [command, '--no-newline', '--type', chosen] if wayland else [command, '-selection', 'clipboard', '-t', chosen, '-o']
        data = read_command(args, MAX_FILE if chosen.startswith('image/') else MAX_TEXT, cancellation=cancellation)
        return ('image', data) if chosen.startswith('image/') else ('text', data.decode('utf-8'))
    raise RuntimeError('Clipboard automático disponível no Linux/macOS; cole o caminho do arquivo.')
