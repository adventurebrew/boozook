import io
from contextlib import contextmanager
from struct import Struct
from typing import (
    IO,
    TYPE_CHECKING,
    Any,
    Dict,
    Iterable,
    Iterator,
    List,
    NamedTuple,
    Tuple,
    cast,
)

from pakal.archive import BaseArchive, make_opener, read_file
from pakal.stream import PartialStreamView

if TYPE_CHECKING:
    from pakal.archive import ArchiveIndex

UINT32LE = Struct('<I')
UINT32LE_X4 = Struct('<4I')
FLOAT32LE = Struct('<f')

VERSION_1_0 = 1.0
VERSION_1_5 = 1.5

FILE_ENTRY_1_0 = Struct('<5I')
FILE_ENTRY_1_5 = Struct('<Q4I')


class LPAKFileEntry(NamedTuple):
    data_offset: int
    name_offset: int
    compressed_size: int
    decompressed_size: int
    is_compressed: int


def read_uint32le_x4(stream: IO[bytes]) -> Tuple[int, int, int, int]:
    return cast(
        Tuple[int, int, int, int],
        UINT32LE_X4.unpack(stream.read(UINT32LE_X4.size)),
    )


def read_float(stream: IO[bytes]) -> float:
    return cast(float, FLOAT32LE.unpack(stream.read(FLOAT32LE.size))[0])


def read_iter(structure: Struct, stream: IO[bytes]) -> Iterator[Tuple[Any, ...]]:
    return structure.iter_unpack(stream.read())


def get_partial_streams(
    stream: IO[bytes],
    cues: Iterable[Tuple[int, int]],
) -> Iterator[Tuple[int, IO[bytes]]]:
    pos = stream.tell()
    for offset, size in cues:
        stream.seek(offset, io.SEEK_SET)
        yield offset, cast(IO[bytes], PartialStreamView(stream, size))
    stream.seek(pos, io.SEEK_SET)


def get_stream_size(stream: IO[bytes]) -> int:
    pos = stream.tell()
    stream.seek(0, io.SEEK_END)
    size = stream.tell()
    stream.seek(pos, io.SEEK_SET)
    return size


def read_header(
    stream: IO[bytes],
) -> Tuple[bytes, float, List[Tuple[int, IO[bytes]]]]:
    size = get_stream_size(stream)
    tag = stream.read(4)
    assert tag == b'LPAK'[::-1]
    version = read_float(stream)
    if version >= VERSION_1_5:
        assert version == VERSION_1_5, version
        offs = list(read_uint32le_x4(stream))
        sizes = list(read_uint32le_x4(stream))
        resizes = sizes[1], sizes[0], sizes[2], size - offs[0]
        cues = list(zip(offs, resizes))
        views = list(get_partial_streams(stream, cues))
        return tag, version, views
    assert version == VERSION_1_0, version
    cues = list(
        zip(
            *[
                read_uint32le_x4(stream),
                read_uint32le_x4(stream),
            ],
        ),  # type: ignore[arg-type]
    )
    views = list(get_partial_streams(stream, cues))
    return tag, version, views


def get_findex(
    stream: IO[bytes],
    views: List[Tuple[int, IO[bytes]]],
) -> Tuple[Dict[str, LPAKFileEntry], int]:
    index, ftable, names, data = views
    assert stream.tell() == index[0]
    _ = [val[0] for val in read_iter(UINT32LE, index[1])]
    assert stream.tell() == ftable[0]
    rftable = [LPAKFileEntry(*val) for val in read_iter(FILE_ENTRY_1_0, ftable[1])]
    assert stream.tell() == names[0]
    rnames = [name.decode() for name in names[1].read().split(b'\0')]
    assert stream.tell() == data[0]
    findex = dict(zip(rnames, rftable))
    return findex, data[0]


def get_findex_v15(
    stream: IO[bytes],
    views: List[Tuple[int, IO[bytes]]],
) -> Tuple[Dict[str, LPAKFileEntry], int]:
    ftable, index, names, data = views
    _ = stream.read(8)
    assert stream.tell() == ftable[0], (stream.tell(), ftable[0])
    rftable = [LPAKFileEntry(*val) for val in read_iter(FILE_ENTRY_1_5, ftable[1])]
    assert stream.tell() == index[0], (stream.tell(), index[0])
    _ = [val[0] for val in read_iter(UINT32LE, index[1])]
    assert stream.tell() == names[0]
    rnames = [name.decode() for name in names[1].read().split(b'\0')]
    assert stream.tell() == data[0]
    findex = dict(zip(rnames, rftable))
    return findex, data[0]


class LPakArchive(BaseArchive[LPAKFileEntry]):
    def _create_index(self) -> 'ArchiveIndex[LPAKFileEntry]':
        tag, version, views = read_header(self._stream)
        self.version = version
        read_findex = get_findex if version < VERSION_1_5 else get_findex_v15
        index, data = read_findex(self._stream, views)
        self.data_off = data
        return index

    @contextmanager
    def _read_entry(self, entry: LPAKFileEntry) -> Iterator[IO[bytes]]:
        yield read_file(
            self._stream,
            self.data_off + entry.data_offset,
            entry.compressed_size,
        )


open = make_opener(LPakArchive)
