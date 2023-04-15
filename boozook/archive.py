from collections import defaultdict
from dataclasses import dataclass, field
import itertools
import os
from pathlib import Path
from typing import Iterable, Iterator, MutableMapping, Optional, Sequence

from boozook.codex import stk
from boozook.codex.stk_compress import recompress_archive


ARCHIVE_PATTERN = '*.STK'


def game_search(base_dir, patterns=('*',), patches=()):
    parsed_files = set()

    base_dir = Path(base_dir)

    if patches is not None:
        for rp in itertools.chain(patches, ('.',)):
            patch_dir = base_dir / rp
            for text_pattern in patterns:
                for entry in sorted(patch_dir.glob(text_pattern)):
                    if not (entry.is_dir() or entry.name in parsed_files):
                        parsed_files.add(entry.name)
                        yield text_pattern, entry

    for archive_path in sorted(base_dir.glob(ARCHIVE_PATTERN)):
        with stk.open(archive_path) as archive:
            for text_pattern in patterns:
                for entry in archive.glob(text_pattern):
                    if entry.name not in parsed_files:
                        parsed_files.add(entry.name)
                        yield text_pattern, entry


@dataclass
class GameBase:
    base_dir: str
    patches: Optional[Sequence[str]]

    _patched: dict[tuple[str, str], bytes] = field(default_factory=dict)

    def search(self, patterns):
        return game_search(self.base_dir, patterns=patterns, patches=self.patches)

    def patch(self, fname: str, data: bytes, alias: str | None = None):
        if not alias:
            alias = fname
        self._patched[(fname, alias)] = data

    def rebuild(self, target='patch'):
        target = Path(target)
        os.makedirs(target, exist_ok=True)
        patches = defaultdict(dict)
        for (fname, alias), data in self._patched.items():
            print(f'should patch {fname} as {alias}')
            for pattern, entry in self.search([fname]):
                if isinstance(entry, Path):
                    (target / entry.name).write_bytes(data)
                else:
                    print(
                        f'Patch {fname} as {alias} in {Path(entry.archive._filename).name}'
                    )
                    patches[Path(entry.archive._filename).name][alias] = data
                break
            else:
                raise ValueError(f'entry {fname} was not found in game')
        for arc, patch in patches.items():
            for pattern, entry in self.search([arc]):
                with stk.open(entry) as archive:
                    recompress_archive(archive, patch, target / entry.name)
                break
            else:
                raise ValueError(f'archive {arc} was not found')


def open_game(base_dir, patches=()):
    return GameBase(base_dir, patches=patches)


class DirectoryBackedArchive(MutableMapping[str, bytes]):
    def __init__(self, directory: str | Path, allowed: Iterable[str] = ()) -> None:
        self.directory = Path(directory)
        self._allowed = frozenset(allowed)
        self._popped = set()
        self._cache: dict[str, bytes] = {}

    def __setitem__(self, key: str, content: bytes) -> None:
        if key not in self._allowed:
            raise KeyError(key)
        Path(key).write_bytes(content)
        self._cache[key] = content

    def __getitem__(self, key: str) -> bytes:
        if key in self._cache:
            return self._cache[key]
        if key not in self._allowed:
            raise KeyError(key)
        return (self.directory / key).read_bytes()

    def __iter__(self) -> Iterator[str]:
        return iter(
            sorted(fname for fname in self._allowed if fname not in self._popped)
        )

    def __len__(self) -> int:
        return len(set(iter(self)))

    def __delitem__(self, key: str) -> None:
        self._cache.pop(key, None)
        self._popped.add(key)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='extract pak archive')
    parser.add_argument('directory', help='game directory with files to extract')
    parser.add_argument(
        '--extract', '-e', action='store_true', help='extract game archives'
    )
    parser.add_argument(
        '--compress',
        '-c',
        action='store_true',
        help='recompress game archives',
    )
    args = parser.parse_args()

    extract_dir = Path('extracted')
    os.makedirs(extract_dir, exist_ok=True)

    game = open_game(args.directory)
    if args.extract:
        for pattern, entry in game.search([ARCHIVE_PATTERN]):
            base_archive = entry.name
            ext_archive = extract_dir / base_archive
            os.makedirs(ext_archive, exist_ok=True)
            with stk.open(entry) as archive:
                for file in archive:
                    (ext_archive / file.name).write_bytes(file.read_bytes())
                    # print(
                    #     file.name,
                    #     int(archive.index[file.name].compression),
                    # )
    if args.compress:
        patch_dir = Path('patch')
        os.makedirs(patch_dir, exist_ok=True)
        for pattern, entry in game.search([ARCHIVE_PATTERN]):
            base_archive = entry.name
            ext_archive = extract_dir / base_archive
            if ext_archive.is_dir():
                patches = DirectoryBackedArchive(
                    ext_archive,
                    allowed={x.name for x in ext_archive.iterdir()},
                )
                with stk.open(entry) as archive:
                    recompress_archive(archive, patches, patch_dir / entry.name)