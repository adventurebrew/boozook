import operator
from functools import partial
from itertools import chain, takewhile
from typing import IO, Iterable, cast


def read_uint16_le(stream: IO[bytes]) -> int:
    return int.from_bytes(stream.read(2), byteorder='little', signed=False)


def read_uint16_be(stream: IO[bytes]) -> int:
    return int.from_bytes(stream.read(2), byteorder='big', signed=False)


def read_uint32_le(stream: IO[bytes]) -> int:
    return int.from_bytes(stream.read(4), byteorder='little', signed=False)


def readcstr(stream: IO[bytes]) -> bytes:
    return b''.join(iter(partial(stream.read, 1), b'\00'))


def bound_readcstr(stream: IO[bytes]) -> bytes:
    return b''.join(
        takewhile(partial(operator.ne, b'\00'), iter(partial(stream.read, 1), b'')),
    )


class ReachedEOFBeforeNullTerminationError(EOFError):
    def __init__(self) -> None:
        super().__init__('Expected null-termination but reached EOF')


def safe_readcstr(stream: IO[bytes]) -> bytes:
    try:
        bound_read = cast(
            Iterable[bytes],
            chain(iter(partial(stream.read, 1), b''), [None]),
        )
    except TypeError as exc:
        raise ReachedEOFBeforeNullTerminationError from exc
    return b''.join(takewhile(partial(operator.ne, b'\00'), bound_read))


def write_uint16_be(number: int) -> bytes:
    return number.to_bytes(2, byteorder='big', signed=False)


def write_uint16_le(number: int) -> bytes:
    return number.to_bytes(2, byteorder='little', signed=False)


def write_uint32_be(number: int) -> bytes:
    return number.to_bytes(4, byteorder='big', signed=False)


def write_uint32_le(number: int) -> bytes:
    return number.to_bytes(4, byteorder='little', signed=False)
