import io
import typing as t

class _NonClosingTextIOWrapper(io.TextIOWrapper):

    def __init__(self, stream: t.BinaryIO, encoding: t.Optional[str], errors: t.Optional[str], force_readable: bool=False, force_writable: bool=False, **extra: t.Any) -> None:
        self._stream = stream = t.cast(t.BinaryIO, _FixupStream(stream, force_readable, force_writable))
        super().__init__(stream, encoding, errors, **extra)

    def __del__(self) -> None:
        try:
            self.detach()
        except Exception:
            pass

class _FixupStream:
    """The new io interface needs more from streams than streams
    traditionally implement.  As such, this fix-up code is necessary in
    some circumstances.

    The forcing of readable and writable flags are there because some tools
    put badly patched objects on sys (one such offender are certain version
    of jupyter notebook).
    """

    def __init__(self, stream: t.BinaryIO, force_readable: bool=False, force_writable: bool=False):
        self._stream = stream
        self._force_readable = force_readable
        self._force_writable = force_writable

    def __getattr__(self, name: str) -> t.Any:
        return getattr(self._stream, name)