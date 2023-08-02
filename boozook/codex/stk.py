import io
from contextlib import contextmanager
from typing import IO, TYPE_CHECKING, AnyStr, Iterator, NamedTuple, Tuple, cast

from pakal.archive import BaseArchive, make_opener
from pakal.examples.common import read_uint16_le, read_uint32_le
from pakal.stream import PartialStreamView

if TYPE_CHECKING:
    from pakal.archive import ArchiveIndex


class STKFileEntry(NamedTuple):
    offset: int
    size: int
    compression: int


def replace_many(s: AnyStr, *reps: Tuple[AnyStr, AnyStr]) -> AnyStr:
    for r in reps:
        s = s.replace(*r)
    return s


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


class STKArchive(BaseArchive[STKFileEntry]):
    def _create_index(self) -> 'ArchiveIndex[STKFileEntry]':
        return dict(extract(self._stream))

    @contextmanager
    def _read_entry(self, entry: STKFileEntry) -> Iterator[IO[bytes]]:
        yield unpack(self._stream, entry.offset, entry.size, entry.compression)


open = make_opener(STKArchive)
