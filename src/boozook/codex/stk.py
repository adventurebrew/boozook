from datetime import datetime
import io
from contextlib import contextmanager
from typing import IO, TYPE_CHECKING, AnyStr, Iterator, NamedTuple, Tuple, cast

from pakal.archive import BaseArchive, make_opener
from pakal.examples.common import read_uint16_le, read_uint32_le, safe_readcstr
from pakal.stream import PartialStreamView

if TYPE_CHECKING:
    from pakal.archive import ArchiveIndex


class STKFileEntry(NamedTuple):
    offset: int
    size: int
    compression: int


class STK21FileEntry(NamedTuple):
    offset: int
    size: int
    compression: int
    uncompressed_size: int
    modified: datetime
    created: datetime
    creator: str
    unk: bytes


def replace_many(s: AnyStr, *reps: Tuple[AnyStr, AnyStr]) -> AnyStr:
    for r in reps:
        s = s.replace(*r)
    return s


def extract_stk21(stream):
    _date = stream.read(14)
    _creator = stream.read(8)
    file_names_offset = read_uint32_le(stream)
    stream.seek(file_names_offset)
    file_count = read_uint32_le(stream)
    misc_offset = read_uint32_le(stream)
    for cpt in range(file_count):
        stream.seek(misc_offset + cpt * 61)
        filename_offset = read_uint32_le(stream)
        modified = datetime.strptime(stream.read(14).decode(), '%d%m%Y%H%M%S')
        created = datetime.strptime(stream.read(14).decode(), '%d%m%Y%H%M%S')
        creator = stream.read(8).split(b'\0')[0].decode()
        size = read_uint32_le(stream)
        uncompressed_size = read_uint32_le(stream)
        unk = stream.read(5)
        offset = read_uint32_le(stream)
        compression = read_uint32_le(stream)
        stream.seek(filename_offset)
        file_name = safe_readcstr(stream).decode()
        yield file_name, STK21FileEntry(offset, size, compression, uncompressed_size, modified, created, creator, unk)


def extract(stream: IO[bytes]) -> Iterator[Tuple[str, STKFileEntry]]:
    file_count = read_uint16_le(stream)
    for _i in range(file_count):
        raw_fname = stream.read(13)
        file_name = raw_fname.split(b'\0')[0].decode()
        size = read_uint32_le(stream)
        offset = read_uint32_le(stream)
        # assert offset % 2 == 0, offset
        compression = stream.read(1) != b'\00'
        if file_name.upper().endswith('.0OT'):
            compression = 2
            file_name = file_name.replace('.0OT', '.TOT')

        # Replacing cyrillic characters
        reps = ('\x85', 'E'), ('\x8A', 'K'), ('\x8E', 'O'), ('\x91', 'C'), ('\x92', 'T')
        file_name = replace_many(file_name, *reps)

        yield file_name, STKFileEntry(offset, size, compression)


def unpack_chunk(stream: IO[bytes], size: int) -> bytes:
    buffer_index = 4078
    buffer = bytearray(b'\x20' * buffer_index + b'\0' * 36)
    result = b''

    command = 0
    while True:
        command >>= 1
        if command & 0x0100 == 0:
            command = ord(stream.read(1)) | 0xFF00

        if command & 1 != 0:
            temp = stream.read(1)
            result += temp
            buffer[buffer_index] = ord(temp)
            buffer_index += 1
            buffer_index %= 4096
            size -= 1
            if not size:
                break
        else:
            hi, low = stream.read(2)

            offset = hi | ((low & 0xF0) << 4)
            length = (low & 0x0F) + 3

            for i in range(length):
                result += bytes([buffer[(offset + i) % 4096]])
                size -= 1
                if not size:
                    return bytes(result)

                buffer[buffer_index] = buffer[(offset + i) % 4096]
                buffer_index += 1
                buffer_index %= 4096

    return bytes(result)


def unpack_chunks(view):
    chunk_size = 0
    data = bytearray()
    uncompressed_size = 0
    while chunk_size != 0xFFFF:
        pos = view.tell()
        chunk_size = read_uint16_le(view)
        real_size = read_uint16_le(view)
        uncompressed_size += real_size

        assert chunk_size >= 4
        view.read(2)
        data += unpack_chunk(view, real_size)
        if chunk_size != 0xFFFF:
            assert view.tell() == pos + chunk_size + 2
    assert len(data) == uncompressed_size
    return bytes(data)


def unpack(stream: IO[bytes], offset: int, size: int, compression: int) -> IO[bytes]:
    stream.seek(offset)
    view = cast(IO[bytes], PartialStreamView(stream, size))
    if not compression:
        return view
    if compression == 2:
        return io.BytesIO(unpack_chunks(view))
    uncompressed_size = read_uint32_le(view)
    return io.BytesIO(unpack_chunk(view, uncompressed_size))


class STKArchive(BaseArchive[STKFileEntry | STK21FileEntry]):
    def _create_index(self) -> 'ArchiveIndex[STKFileEntry | STK21FileEntry]':
        header = self._stream.read(6)
        if header == b'STK2.1':
            self.version = 2.1
            return dict(extract_stk21(self._stream))
        self._stream.seek(0, io.SEEK_SET)
        self.version = 1
        return dict(extract(self._stream))

    @contextmanager
    def _read_entry(self, entry: STKFileEntry | STK21FileEntry) -> Iterator[IO[bytes]]:
        res = unpack(self._stream, entry.offset, entry.size, entry.compression)
        if isinstance(entry, STK21FileEntry) and entry.uncompressed_size is not None:
            res.seek(0, io.SEEK_END)
            assert res.tell() == entry.uncompressed_size, (res.tell(), entry.uncompressed_size)
            res.seek(0, io.SEEK_SET)
        yield res


open = make_opener(STKArchive)
