import io
import operator
import os
from enum import IntEnum
from itertools import groupby
from typing import Iterable, Sequence
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
    lines: Iterable[Sequence[str]],
) -> None:
    grouped = groupby(lines, key=operator.itemgetter('FILE'))
    for tfname, group in grouped:
        basename = os.path.basename(tfname)
        group = list(group)
        for pattern, entry in game.search([basename]):
            with entry.open('rb') as f, io.BytesIO() as output:
                version = f.read(18)
                num_messages = version[4]
                output.write(version)

                for lang in Language:
                    pos = len(version) + lang * num_messages * LINE_SIZE
                    assert output.tell() == pos, (output.tell(), pos)
                    for line in group:
                        enc = line[lang.name]
                        if enc is None:
                            output.seek(LINE_SIZE, io.SEEK_CUR)
                            continue
                        towrite = enc.ljust(LINE_SIZE, b'\0')
                        assert len(towrite) == LINE_SIZE, len(towrite)
                        output.write(towrite)

                game.patch(
                    entry.name,
                    output.getvalue(),
                )


def write_parsed(
    game: GameBase,
    entry: ArchivePath,
) -> None:
    with entry.open('rb') as f:
        version = f.read(18)
        num_messages = version[4]
        print(version)
        text_line = [{} for num in range(num_messages)]
        for lang in Language:
            for num in range(num_messages):
                line = f.read(LINE_SIZE)
                if not line:
                    break
                line, rest = line.split(b'\0', maxsplit=1)
                assert set(rest) == {0} or set(rest) == {0, ord(' ')}, rest
                text_line[num][lang.name] = line
        yield from text_line