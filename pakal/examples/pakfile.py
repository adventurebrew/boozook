from functools import partial
from itertools import takewhile
from typing import IO, TYPE_CHECKING, Any, Iterable, Sequence, Tuple

from pakal.archive import SimpleArchive, make_opener
from pakal.examples.common import read_uint32_le, readcstr

if TYPE_CHECKING:
    from pakal.archive import ArchiveIndex, SimpleEntry


def read_index_entry(stream: IO[bytes]) -> Tuple[str, int]:
    return readcstr(stream).decode(), read_uint32_le(stream)


def before_offset(stream: IO[bytes], off: int, *args: Any) -> bool:
    return stream.tell() < off


def read_index_entries(stream: IO[bytes]) -> Tuple[Sequence[str], Sequence[int]]:
    off = read_uint32_le(stream)
    index_entries = iter(partial(read_index_entry, stream), ('', 0))
    index_entries = takewhile(partial(before_offset, stream, off), index_entries)
    names, offs = zip(*index_entries)
    return names, (off, *tuple(offs))


def create_index_mapping(
    names: Iterable[str],
    offsets: Sequence[int],
) -> 'ArchiveIndex[SimpleEntry]':
    sizes = [(end - start) for start, end in zip(offsets, offsets[1:])]
    return dict(zip(names, zip(offsets, sizes)))


class PakFile(SimpleArchive):
    def _create_index(self) -> 'ArchiveIndex[SimpleEntry]':
        return create_index_mapping(*read_index_entries(self._stream))


open = make_opener(PakFile)
