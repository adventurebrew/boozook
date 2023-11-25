import io
from typing import IO, AnyStr, Generic, Optional, Union

Stream = Union[IO[AnyStr], 'PartialStreamView']
AnyStream = Union[Stream[str], Stream[bytes]]


class PartialStreamView(Generic[AnyStr]):
    def __init__(self, stream: Stream[AnyStr], size: int) -> None:
        self._stream: Stream[AnyStr] = stream
        self._start = stream.tell()
        if isinstance(self._stream, PartialStreamView):
            self._start += self._stream._start  # noqa: private-member-access
            self._stream = self._stream._stream  # noqa: private-member-access
        self._size = size
        self._pos = 0

    def seek(self, pos: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_CUR:
            pos += self._pos
        elif whence == io.SEEK_END:
            pos += self._size
        self._pos = pos
        return self._pos

    def tell(self) -> int:
        return self._pos

    def read(self, size: Optional[int] = None) -> AnyStr:
        self._stream.seek(self._start + self._pos, io.SEEK_SET)
        if size is not None and size >= 0:
            size = min(self._size - self._pos, size)
        else:
            size = self._size - self._pos
        res = self._stream.read(size)
        self._pos += len(res)
        return res
