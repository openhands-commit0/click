import codecs
import io
import os
import re
import sys
import typing as t
from functools import update_wrapper
from weakref import WeakKeyDictionary

CYGWIN = sys.platform.startswith('cygwin')
WIN = sys.platform.startswith('win')
auto_wrap_for_ansi: t.Optional[t.Callable[[t.TextIO], t.TextIO]] = None
_ansi_re = re.compile('\\033\\[[;?0-9]*[a-zA-Z]')

def _make_cached_stream_func(factory: t.Callable[[], t.IO[t.Any]], wrapper_factory: t.Callable[..., t.IO[t.Any]]) -> t.Callable[..., t.IO[t.Any]]:
    """Creates a function that returns a cached stream based on the factory.
    
    The stream is cached on first access and reused on subsequent calls.
    """
    cache: t.Dict[int, t.IO[t.Any]] = {}

    def get_stream(*args: t.Any, **kwargs: t.Any) -> t.IO[t.Any]:
        pid = os.getpid()
        stream = cache.get(pid)

        if stream is None:
            stream = wrapper_factory(factory(), *args, **kwargs)
            cache[pid] = stream

        return stream

    return update_wrapper(get_stream, wrapper_factory)

def _get_argv_encoding() -> str:
    """Get the encoding for argv on the current platform."""
    return getattr(sys.stdin, 'encoding', None) or sys.getfilesystemencoding() or 'utf-8'

def is_ascii_encoding(encoding: str) -> bool:
    """Checks if a given encoding is ascii."""
    try:
        return codecs.lookup(encoding).name == 'ascii'
    except LookupError:
        return False

def get_best_encoding(stream: t.IO[t.Any]) -> str:
    """Returns the default stream encoding if not found."""
    rv = getattr(stream, 'encoding', None) or sys.getdefaultencoding()
    return rv if not is_ascii_encoding(rv) else 'utf-8'

def _stream_is_misconfigured(stream: t.TextIO) -> bool:
    """A stream is misconfigured if its encoding is ASCII."""
    return is_ascii_encoding(getattr(stream, 'encoding', None) or '')

def _is_compat_stream_attr(stream: t.TextIO, attr: str, value: t.Optional[str]) -> bool:
    """A stream attribute is compatible if it is equal to the
    desired value or the desired value is unset and the attribute
    has a value.
    """
    stream_value = getattr(stream, attr, None)
    return stream_value == value or (value is None and stream_value is not None)

def _is_compatible_text_stream(stream: t.TextIO, encoding: t.Optional[str], errors: t.Optional[str]) -> bool:
    """Check if a stream's encoding and errors attributes are
    compatible with the desired values.
    """
    return _is_compat_stream_attr(stream, 'encoding', encoding) and _is_compat_stream_attr(stream, 'errors', errors)

def _wrap_io_open(file: t.Union[str, 'os.PathLike[str]', int], mode: str, encoding: t.Optional[str], errors: t.Optional[str]) -> t.IO[t.Any]:
    """Handles not passing ``encoding`` and ``errors`` in binary mode."""
    if 'b' in mode:
        return open(file, mode)
    return open(file, mode, encoding=encoding, errors=errors)

def _find_binary_reader(stream: t.IO[t.Any]) -> t.BinaryIO:
    """Find a binary reader for the given stream."""
    if isinstance(stream, (io.RawIOBase, io.BufferedIOBase)):
        return t.cast(t.BinaryIO, stream)
    buffer = getattr(stream, 'buffer', None)
    if buffer is not None:
        return t.cast(t.BinaryIO, buffer)
    return t.cast(t.BinaryIO, stream)

def _find_binary_writer(stream: t.IO[t.Any]) -> t.BinaryIO:
    """Find a binary writer for the given stream."""
    if isinstance(stream, (io.RawIOBase, io.BufferedIOBase)):
        return t.cast(t.BinaryIO, stream)
    buffer = getattr(stream, 'buffer', None)
    if buffer is not None:
        return t.cast(t.BinaryIO, buffer)
    return t.cast(t.BinaryIO, stream)

def open_stream(filename: t.Union[str, 'os.PathLike[str]', int], mode: str='r', encoding: t.Optional[str]=None, errors: t.Optional[str]='strict', atomic: bool=False) -> t.Tuple[t.IO[t.Any], bool]:
    """Open a file or stream."""
    if isinstance(filename, int):
        if 'w' in mode:
            return _find_binary_writer(sys.stdout), False
        return _find_binary_reader(sys.stdin), False

    if 'b' in mode:
        return _wrap_io_open(filename, mode, None, None), True

    encoding = encoding or _get_argv_encoding()
    return _wrap_io_open(filename, mode, encoding, errors), True

def should_strip_ansi(stream: t.Optional[t.IO[t.Any]]=None, color: t.Optional[bool]=None) -> bool:
    """Determine if ANSI escape sequences should be stripped from the output."""
    if color is None:
        return not isatty(stream)
    return not color

def strip_ansi(value: str) -> str:
    """Strip ANSI escape sequences from a string."""
    return _ansi_re.sub('', value)

def isatty(stream: t.Optional[t.IO[t.Any]]) -> bool:
    """Check if a stream is a TTY."""
    if stream is None:
        stream = sys.stdout
    try:
        return stream.isatty()
    except Exception:
        return False

def term_len(x: str) -> int:
    """Return the length of a string, taking into account ANSI escape sequences."""
    return len(strip_ansi(x))

from ._wrappers import _NonClosingTextIOWrapper

class _AtomicFile:

    def __init__(self, f: t.IO[t.Any], tmp_filename: str, real_filename: str) -> None:
        self._f = f
        self._tmp_filename = tmp_filename
        self._real_filename = real_filename
        self.closed = False

    def __getattr__(self, name: str) -> t.Any:
        return getattr(self._f, name)

    def __enter__(self) -> '_AtomicFile':
        return self

    def __exit__(self, exc_type: t.Optional[t.Type[BaseException]], *_: t.Any) -> None:
        self.close(delete=exc_type is not None)

    def __repr__(self) -> str:
        return repr(self._f)

def get_binary_stdin() -> t.BinaryIO:
    return sys.stdin.buffer

def get_binary_stdout() -> t.BinaryIO:
    return sys.stdout.buffer

def get_binary_stderr() -> t.BinaryIO:
    return sys.stderr.buffer

def get_text_stdin(encoding: t.Optional[str]=None, errors: t.Optional[str]=None) -> t.TextIO:
    if encoding is None:
        encoding = get_best_encoding(sys.stdin)
    if errors is None:
        errors = 'replace'
    if _stream_is_misconfigured(sys.stdin):
        return _NonClosingTextIOWrapper(sys.stdin.buffer, encoding, errors)
    return sys.stdin

def get_text_stdout(encoding: t.Optional[str]=None, errors: t.Optional[str]=None) -> t.TextIO:
    if encoding is None:
        encoding = get_best_encoding(sys.stdout)
    if errors is None:
        errors = 'replace'
    if _stream_is_misconfigured(sys.stdout):
        return _NonClosingTextIOWrapper(sys.stdout.buffer, encoding, errors)
    return sys.stdout

def get_text_stderr(encoding: t.Optional[str]=None, errors: t.Optional[str]=None) -> t.TextIO:
    if encoding is None:
        encoding = get_best_encoding(sys.stderr)
    if errors is None:
        errors = 'replace'
    if _stream_is_misconfigured(sys.stderr):
        return _NonClosingTextIOWrapper(sys.stderr.buffer, encoding, errors)
    return sys.stderr

if sys.platform.startswith('win') and WIN:
    from ._winconsole import _get_windows_console_stream
    _ansi_stream_wrappers: t.MutableMapping[t.TextIO, t.TextIO] = WeakKeyDictionary()

    def auto_wrap_for_ansi(stream: t.TextIO, color: t.Optional[bool]=None) -> t.TextIO:
        """Support ANSI color and style codes on Windows by wrapping a
        stream with colorama.
        """
        try:
            cached = _ansi_stream_wrappers.get(stream)
            if cached is not None:
                return cached
            
            import colorama
            strip = not color if color is not None else not colorama.enable
            wrapped = colorama.AnsiToWin32(stream, strip=strip).stream
            _ansi_stream_wrappers[stream] = wrapped
            return wrapped
        except ImportError:
            return stream

_default_text_stdin = _make_cached_stream_func(lambda: sys.stdin, get_text_stdin)
_default_text_stdout = _make_cached_stream_func(lambda: sys.stdout, get_text_stdout)
_default_text_stderr = _make_cached_stream_func(lambda: sys.stderr, get_text_stderr)
binary_streams: t.Mapping[str, t.Callable[[], t.BinaryIO]] = {'stdin': get_binary_stdin, 'stdout': get_binary_stdout, 'stderr': get_binary_stderr}
text_streams: t.Mapping[str, t.Callable[[t.Optional[str], t.Optional[str]], t.TextIO]] = {'stdin': get_text_stdin, 'stdout': get_text_stdout, 'stderr': get_text_stderr}