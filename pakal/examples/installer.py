import io
import os
from typing import IO, TYPE_CHECKING

from pakal.archive import SimpleArchive, make_opener
from pakal.examples.common import read_uint32_le

if TYPE_CHECKING:
    from pakal.archive import ArchiveIndex, SimpleEntry


def read_index_entries(stream: IO[bytes]) -> 'ArchiveIndex[SimpleEntry]':
    _unk = stream.read(3)
    size = read_uint32_le(stream)
    subs = stream.read(size).split(b'\r\n')[:-1]
    index = {}
    for i in subs:
        size = read_uint32_le(stream)
        offset = stream.tell()
        index[os.path.basename(i).decode('ascii')] = (offset, size)
        stream.seek(size, io.SEEK_CUR)
    rest = stream.read()
    assert not rest, rest
    return index


class WestwoodInstaller(SimpleArchive):
    def _create_index(self) -> 'ArchiveIndex[SimpleEntry]':
        return read_index_entries(self._stream)


open = make_opener(WestwoodInstaller)
