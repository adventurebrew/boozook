import io
import os
import pathlib
from contextlib import AbstractContextManager, contextmanager
from typing import (
    IO,
    TYPE_CHECKING,
    Any,
    AnyStr,
    Callable,
    ContextManager,
    Generic,
    Iterator,
    Mapping,
    NamedTuple,
    Optional,
    Protocol,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

if TYPE_CHECKING:
    from types import TracebackType

from pakal.stream import PartialStreamView

GLOB_ALL = '*'


EntryType = TypeVar('EntryType')
ArchiveIndex = Mapping[str, EntryType]


class _SimpleEntry(NamedTuple):
    offset: int
    size: int


class Opener(Protocol):
    def open(
        self,
        file: Union[str, bytes, os.PathLike[AnyStr]],
        mode: str,
        **kwars: Any,
    ) -> IO[AnyStr]:
        """Custom namespace that provides `open` function."""


SimpleEntry = Union[_SimpleEntry, Tuple[int, int]]


def read_file(stream: IO[bytes], offset: int, size: int) -> IO[bytes]:
    stream.seek(
        offset,
        io.SEEK_SET,
    )  # need unit test to check offset is always equal to f.tell()
    return cast(IO[bytes], PartialStreamView(stream, size))


class MemberNotFoundError(ValueError):
    def __init__(self, fname: str) -> None:
        super().__init__(f'no member {fname} found in archive')


class ArchivePath:
    def __init__(
        self,
        fname: Union[str, os.PathLike[str]],
        archive: 'BaseArchive[EntryType]',
    ) -> None:
        self.fname = pathlib.Path(os.path.normpath(fname))
        self.archive = archive

    @property
    def parent(self) -> 'ArchivePath':
        """The logical parent of the path."""
        return ArchivePath(self.fname.parent, self.archive)

    @property
    def name(self) -> str:
        """The final path component, if any."""
        return str(self.fname.name)

    @property
    def suffix(self) -> str:
        """
        The final component's last suffix, if any.

        This includes the leading period. For example: '.txt'
        """
        return str(self.fname.suffix)

    @property
    def stem(self) -> str:
        """The final path component, minus its last suffix."""
        return str(self.fname.stem)

    def with_name(self, name: str) -> 'ArchivePath':
        """Return a new path with the file name changed."""
        return ArchivePath(self.fname.with_name(name), self.archive)

    def with_stem(self, stem: str) -> 'ArchivePath':
        """Return a new path with the stem changed."""
        return ArchivePath(self.fname.with_stem(stem), self.archive)

    def with_suffix(self, suffix: str) -> 'ArchivePath':
        """Return a new path with the file suffix changed."""
        return ArchivePath(self.fname.with_suffix(suffix), self.archive)

    def __str__(self) -> str:
        """Return the string representation of the path."""
        return str(self.fname)

    def match(self, pattern: str) -> bool:
        """
        Return True if this path matches the given pattern.
        """
        return self.fname.match(pattern)

    def exists(self) -> bool:
        """Returns True if this path exists within the archive."""
        return any(self.archive.glob(str(self)))

    def glob(self, pattern: str) -> Iterator['ArchivePath']:
        """Iterate over this subtree and yield all existing files (of any
        kind, including directories) matching the given relative pattern.
        """
        return (
            entry for entry in self.archive if entry.match(str(self.fname / pattern))
        )

    def open(
        self,
        mode: str = 'r',
        encoding: str = 'utf-8',
        errors: Optional[str] = None,
    ) -> ContextManager[IO[AnyStr]]:
        """
        Open the file pointed by this path and return a file object, as
        the built-in open() function does.
        """
        return self.archive.open(
            self.fname,
            mode=mode,
            encoding=encoding,
            errors=errors,
        )

    def read_bytes(self) -> bytes:
        """
        Open the file in bytes mode, read it, and close the file.
        """
        with self.open(mode='rb') as stream:
            return cast(bytes, stream.read())

    def read_text(
        self,
        encoding: str = 'utf-8',
        errors: Optional[str] = None,
    ) -> str:
        """
        Open the file in text mode, read it, and close the file.
        """
        with self.open(
            mode='r',
            encoding=encoding,
            errors=errors,
        ) as stream:
            return stream.read()

    def __truediv__(self, key: Union[str, os.PathLike[str]]) -> 'ArchivePath':
        return ArchivePath(str(pathlib.Path(self.fname) / key), self.archive)

    def __rtruediv__(self, key: Union[str, os.PathLike[str]]) -> 'ArchivePath':
        return ArchivePath(str(key / pathlib.Path(self.fname)), self.archive)


class BaseArchive(AbstractContextManager['BaseArchive[EntryType]'], Generic[EntryType]):
    _stream: IO[bytes]

    index: Mapping[str, EntryType]

    _filename: Optional[pathlib.Path] = None
    _io: Opener = io  # type: ignore[assignment]

    def _create_index(self) -> ArchiveIndex[EntryType]:
        raise NotImplementedError('create_index')

    @contextmanager
    def _read_entry(self, entry: EntryType) -> Iterator[IO[bytes]]:
        raise NotImplementedError('read_entry')

    def __init__(
        self,
        file: Union[AnyStr, os.PathLike[AnyStr], IO[bytes]],
        opener: Opener = io,  # type: ignore[assignment]
    ) -> None:
        if isinstance(file, os.PathLike):
            file = os.fspath(file)

        self._io = opener

        if isinstance(file, (str, bytes)):
            self._stream = self._io.open(file, 'rb')
            self._filename = pathlib.Path(file)  # type: ignore[arg-type]
        else:
            self._stream = file
            self._filename = None
        self.index = {
            os.path.normpath(name): entry
            for name, entry in self._create_index().items()
        }

    @contextmanager
    def open(
        self,
        fname: Union[str, os.PathLike[str]],
        mode: str = 'r',
        encoding: str = 'utf-8',
        errors: Optional[str] = None,
    ) -> Iterator[IO[AnyStr]]:
        try:
            member = self.index[os.path.normpath(fname)]
        except KeyError as exc:
            raise MemberNotFoundError(str(fname)) from exc

        ostream: IO  # type: ignore[type-arg]
        with self._read_entry(member) as stream:
            ostream = stream
            if 'b' not in mode:
                ostream = io.TextIOWrapper(
                    cast(IO[bytes], ostream),  # type: ignore[redundant-cast]
                    encoding=encoding,
                    errors=errors,
                )
            yield ostream

    def close(self) -> Optional[bool]:
        return self._stream.close()

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional['TracebackType'],
    ) -> Optional[bool]:
        return self.close()

    def __iter__(self) -> Iterator[ArchivePath]:
        for fname, _ in self.index.items():
            yield ArchivePath(fname, self)

    def glob(self, pattern: str) -> Iterator[ArchivePath]:
        return (entry for entry in self if entry.match(pattern))

    def extractall(
        self,
        dirname: Union[str, os.PathLike[str]],
        pattern: str = GLOB_ALL,
    ) -> None:
        dirname = pathlib.Path(dirname)
        for entry in self.glob(pattern):
            os.makedirs(str(dirname / entry.parent), exist_ok=True)
            with io.open(str(dirname / entry.fname), 'wb') as out_file:
                out_file.write(entry.read_bytes())


class SimpleArchive(BaseArchive[SimpleEntry]):
    @contextmanager
    def _read_entry(self, entry: SimpleEntry) -> Iterator[IO[bytes]]:
        entry = _SimpleEntry(*entry)
        yield read_file(self._stream, entry.offset, entry.size)


def make_opener(
    archive_type: Type['BaseArchive[EntryType]'],
) -> Callable[..., ContextManager['BaseArchive[EntryType]']]:
    @contextmanager
    def opener(*args: Any, **kwargs: Any) -> Iterator['BaseArchive[EntryType]']:
        with archive_type(*args, **kwargs) as inst:
            yield inst

    return opener


if __name__ == '__main__':
    import argparse
    from importlib import import_module

    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument(
        '-m',
        '--module',
        required=True,
        type=str,
        help='Archive module',
    )
    parser.add_argument('filename', type=str, help='File to extract from')
    parser.add_argument(
        'pattern',
        type=str,
        nargs='?',
        default=GLOB_ALL,
        help='Pattern of file names to extract',
    )

    args = parser.parse_args()

    open_archive: Callable[..., ContextManager[BaseArchive[Any]]] = import_module(
        args.module,
    ).open

    with open_archive(args.filename) as arc:
        if args.pattern == GLOB_ALL:
            assert {str(x) for x in arc.glob(args.pattern)} == set(arc.index)

        arc.extractall('out', args.pattern)
