from collections.abc import Iterator
import io
import operator
import os
from enum import IntEnum
from itertools import groupby
from typing import Iterable, cast
from boozook.archive import GameBase

from pakal.archive import ArchivePath


LINE_SIZE = 40


class Language(IntEnum):
    DAT = 0
    ALL = 1
    ANG = 2
    ESP = 3
    ITA = 4
    USA = 5
    NDL = 6
    KOR = 7
    ISR = 8
    IDE = 9


def compose(
    game: GameBase,
    lines: Iterable[tuple[str, dict[str, bytes | None]]],
) -> None:
    grouped = groupby(lines, key=operator.itemgetter(0))
    for tfname, group in grouped:
        basename = os.path.basename(tfname)
        cgroup = list(group)
        for pattern, entry in game.search([basename]):
            with entry.open('rb') as f, io.BytesIO() as output:
                version = f.read(18)
                num_messages = version[4]
                output.write(version)

                for lang in Language:
                    pos = len(version) + lang * num_messages * LINE_SIZE
                    assert output.tell() == pos, (output.tell(), pos)
                    for _, line in cgroup:
                        enc = line[lang.name]
                        if enc is None:
                            output.seek(LINE_SIZE, io.SEEK_CUR)
                            continue
                        enc = enc.replace(b'~', b'\0')
                        towrite = enc.ljust(LINE_SIZE, b'\0')
                        if sum(towrite[40:]) > 0:
                            raise ValueError(
                                'Non-null characters after 40 characters limit',
                            )
                        towrite = towrite[:40]
                        assert len(towrite) == LINE_SIZE, len(towrite)
                        output.write(towrite)

                # force write at current stream position (fill with zeros)
                output.write(b'\0')
                game.patch(
                    entry.name,
                    output.getvalue()[:-1],
                )


def write_parsed(
    game: GameBase,
    entry: ArchivePath,
) -> Iterator[dict[str, bytes | None]]:
    with entry.open('rb') as f:
        version = f.read(18)
        num_messages = version[4]
        print(version)
        text_line: list[dict[str, bytes | None]] = [{} for num in range(num_messages)]
        for lang in Language:
            for num in range(num_messages):
                line = cast(bytes, f.read(LINE_SIZE))
                if not line:
                    break
                # line, rest = line.split(b'\0', maxsplit=1)
                # assert set(rest) == {0} or set(rest) == {0, ord(' ')}, rest
                assert b'~' not in line, line
                line = line.replace(b'\0', b'~')
                text_line[num][lang.name] = line
        yield from text_line
