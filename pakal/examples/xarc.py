import pathlib
from typing import IO, TYPE_CHECKING, Iterator, Tuple

from pakal.archive import (
    GLOB_ALL,
    SimpleArchive,
    make_opener,
)
from pakal.examples.common import read_uint32_le, readcstr

if TYPE_CHECKING:
    from pakal.archive import ArchiveIndex, SimpleEntry


def read_index_entries(stream: IO[bytes]) -> Iterator[Tuple[str, 'SimpleEntry']]:
    _unknown = read_uint32_le(stream)
    file_count = read_uint32_le(stream)
    base_offset = read_uint32_le(stream)
    offset = base_offset
    for _i in range(file_count):
        file_name = readcstr(stream).decode('ascii')
        file_size = read_uint32_le(stream)
        _unknown2 = read_uint32_le(stream)
        yield file_name, (offset, file_size)
        offset += file_size


class TLJXArchive(SimpleArchive):
    def _create_index(self) -> 'ArchiveIndex[SimpleEntry]':
        return dict(read_index_entries(self._stream))


open = make_opener(TLJXArchive)

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('basedir', type=str, help='File to extract from')
    parser.add_argument('search_pattern', type=str, help='File to extract from')
    parser.add_argument(
        'extract_pattern',
        type=str,
        nargs='?',
        default=GLOB_ALL,
        help='Pattern of file names to extract',
    )

    args = parser.parse_args()

    open_archive = open

    output_dir = pathlib.Path('out')

    for fname in sorted(pathlib.Path(args.basedir).glob(args.search_pattern)):
        basepath = fname.relative_to(args.basedir).parent / 'xarc'
        with open_archive(fname) as arc:
            if args.extract_pattern == GLOB_ALL:
                assert {str(x) for x in arc.glob(args.extract_pattern)} == set(
                    arc.index,
                )

            arc.extractall(output_dir / basepath, args.extract_pattern)
