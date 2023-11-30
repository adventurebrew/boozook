from functools import partial, wraps
from itertools import chain, takewhile
import operator
from typing import (
    Callable,
    Iterable,
    Optional,
    Protocol,
    TypeVar,
    Union,
    cast,
    ParamSpec,
)


ItemT = TypeVar('ItemT')
ResultT = TypeVar('ResultT')
ArgsP = ParamSpec('ArgsP')
ReadT = TypeVar('ReadT', covariant=True)
BufferLike = Union[bytes, bytearray, memoryview]


class SupportsRead(Protocol[ReadT]):
    def read(self, size: int = ...) -> ReadT:
        ...

    def seek(self, pos: int, whence: int) -> Optional[int]:
        ...

    def tell(self) -> int:
        ...


def collect(
    collector: Callable[[Iterable[ItemT]], ResultT],
) -> Callable[[Callable[ArgsP, Iterable[ItemT]]], Callable[ArgsP, ResultT]]:
    def decorator(
        generator: Callable[ArgsP, Iterable[ItemT]],
    ) -> Callable[ArgsP, ResultT]:
        @wraps(generator)
        def inner(*args: ArgsP.args, **kwargs: ArgsP.kwargs) -> ResultT:
            return collector(generator(*args, **kwargs))

        return inner

    return decorator


def read_uint16_le(stream: SupportsRead[bytes]) -> int:
    return int.from_bytes(stream.read(2), byteorder='little', signed=False)


def read_uint16_be(stream: SupportsRead[bytes]) -> int:
    return int.from_bytes(stream.read(2), byteorder='big', signed=False)


def read_uint32_le(stream: SupportsRead[bytes]) -> int:
    return int.from_bytes(stream.read(4), byteorder='little', signed=False)


def readcstr(stream: SupportsRead[bytes]) -> bytes:
    return b''.join(iter(partial(stream.read, 1), b'\00'))


def bound_readcstr(stream: SupportsRead[bytes]) -> bytes:
    return b''.join(
        takewhile(partial(operator.ne, b'\00'), iter(partial(stream.read, 1), b''))
    )


def safe_readcstr(stream: SupportsRead[bytes]) -> bytes:
    try:
        bound_read = cast(
            Iterable[bytes], chain(iter(partial(stream.read, 1), b''), [None])
        )
        return b''.join(takewhile(partial(operator.ne, b'\00'), bound_read))
    except TypeError:
        raise EOFError('Expected null-termination but reached EOF')


def write_uint16_be(number: int) -> bytes:
    return number.to_bytes(2, byteorder='big', signed=False)


def write_uint16_le(number: int) -> bytes:
    return number.to_bytes(2, byteorder='little', signed=False)


def write_uint32_be(number: int) -> bytes:
    return number.to_bytes(4, byteorder='big', signed=False)


def write_uint32_le(number: int) -> bytes:
    return number.to_bytes(4, byteorder='little', signed=False)
