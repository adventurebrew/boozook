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
        compression = stream.read(1) != b'\00'

        # Replacing cyrillic characters
        reps = ('\x85', 'E'), ('\x8A', 'K'), ('\x8E', 'O'), ('\x91', 'C'), ('\x92', 'T')
        file_name = replace_many(file_name, *reps)

        yield file_name, STKFileEntry(offset, size, compression)


def unpack_chunk(stream: IO[bytes], size: int) -> bytes:
    tmp_ind = 4078
    tmp_buf = bytearray(b'\x20' * tmp_ind + b'\0' * 36)
    res = b''

    cmd = 0
    while True:
        cmd >>= 1
        if cmd & 0x0100 == 0:
            cmd = ord(stream.read(1)) | 0xFF00
        if cmd & 1 != 0:
            tmp = stream.read(1)
            res += tmp
            tmp_buf[tmp_ind] = ord(tmp)
            tmp_ind += 1
            tmp_ind %= 4096
            size -= 1
            if not size:
                break
        else:
            tmp1 = ord(stream.read(1))
            tmp2 = ord(stream.read(1))

            off = tmp1 | ((tmp2 & 0xF0) << 4)
            ln = (tmp2 & 0x0F) + 3

            for i in range(ln):
                res += bytes([tmp_buf[(off + i) % 4096]])
                size -= 1
                if not size:
                    return bytes(res)

                tmp_buf[tmp_ind] = tmp_buf[(off + i) % 4096]
                tmp_ind += 1
                tmp_ind %= 4096
    return bytes(res)


def unpack(stream: IO[bytes], offset: int, size: int, compression: int) -> IO[bytes]:
    stream.seek(offset)
    view = cast(IO[bytes], PartialStreamView(stream, size))
    if not compression:
        return view
    uncompressed_size = read_uint32_le(view)
    return io.BytesIO(unpack_chunk(stream, uncompressed_size))


class STKArchive(BaseArchive[STKFileEntry]):
    def _create_index(self) -> 'ArchiveIndex[STKFileEntry]':
        return dict(extract(self._stream))

    @contextmanager
    def _read_entry(self, entry: STKFileEntry) -> Iterator[IO[bytes]]:
        yield unpack(self._stream, entry.offset, entry.size, entry.compression)


open = make_opener(STKArchive)
