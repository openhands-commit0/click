import io
import sys
import time
import typing as t
from ctypes import byref
from ctypes import c_char
from ctypes import c_char_p
from ctypes import c_int
from ctypes import c_ssize_t
from ctypes import c_ulong
from ctypes import c_void_p
from ctypes import POINTER
from ctypes import py_object
from ctypes import Structure
from ctypes.wintypes import DWORD
from ctypes.wintypes import HANDLE
from ctypes.wintypes import LPCWSTR
from ctypes.wintypes import LPWSTR
from ._wrappers import _NonClosingTextIOWrapper
assert sys.platform == 'win32'
import msvcrt
from ctypes import windll
from ctypes import WINFUNCTYPE
c_ssize_p = POINTER(c_ssize_t)
kernel32 = windll.kernel32
GetStdHandle = kernel32.GetStdHandle
ReadConsoleW = kernel32.ReadConsoleW
WriteConsoleW = kernel32.WriteConsoleW
GetConsoleMode = kernel32.GetConsoleMode
GetLastError = kernel32.GetLastError
GetCommandLineW = WINFUNCTYPE(LPWSTR)(('GetCommandLineW', windll.kernel32))
CommandLineToArgvW = WINFUNCTYPE(POINTER(LPWSTR), LPCWSTR, POINTER(c_int))(('CommandLineToArgvW', windll.shell32))
LocalFree = WINFUNCTYPE(c_void_p, c_void_p)(('LocalFree', windll.kernel32))
STDIN_HANDLE = GetStdHandle(-10)
STDOUT_HANDLE = GetStdHandle(-11)
STDERR_HANDLE = GetStdHandle(-12)
PyBUF_SIMPLE = 0
PyBUF_WRITABLE = 1
ERROR_SUCCESS = 0
ERROR_NOT_ENOUGH_MEMORY = 8
ERROR_OPERATION_ABORTED = 995
STDIN_FILENO = 0
STDOUT_FILENO = 1
STDERR_FILENO = 2
EOF = b'\x1a'
MAX_BYTES_WRITTEN = 32767
try:
    from ctypes import pythonapi
except ImportError:
    get_buffer = None
else:

    class Py_buffer(Structure):
        _fields_ = [('buf', c_void_p), ('obj', py_object), ('len', c_ssize_t), ('itemsize', c_ssize_t), ('readonly', c_int), ('ndim', c_int), ('format', c_char_p), ('shape', c_ssize_p), ('strides', c_ssize_p), ('suboffsets', c_ssize_p), ('internal', c_void_p)]
    PyObject_GetBuffer = pythonapi.PyObject_GetBuffer
    PyBuffer_Release = pythonapi.PyBuffer_Release

class _WindowsConsoleRawIOBase(io.RawIOBase):

    def __init__(self, handle):
        self.handle = handle

class _WindowsConsoleReader(_WindowsConsoleRawIOBase):
    pass

class _WindowsConsoleWriter(_WindowsConsoleRawIOBase):
    pass

class ConsoleStream:

    def __init__(self, text_stream: t.TextIO, byte_stream: t.BinaryIO) -> None:
        self._text_stream = text_stream
        self.buffer = byte_stream

    def __getattr__(self, name: str) -> t.Any:
        return getattr(self._text_stream, name)

    def __repr__(self):
        return f'<ConsoleStream name={self.name!r} encoding={self.encoding!r}>'
_stream_factories: t.Mapping[int, t.Callable[[t.BinaryIO], t.TextIO]] = {0: _get_text_stdin, 1: _get_text_stdout, 2: _get_text_stderr}