import io
import operator
import os
from itertools import groupby
from typing import IO, Iterable, Sequence
from boozook.archive import GameBase

from pakal.archive import ArchivePath


LINE_SIZE = 40
LANGS = {
    'ISR': 8,
    'ANG': 2,
}


def compose(
    game: GameBase,
    lines: Iterable[Sequence[str]],
    lang_code: str = 'ANG',
    encoding: str = 'cp862',
) -> None:
    grouped = groupby(lines, key=operator.itemgetter(0))
    for tfname, group in grouped:
        basename = os.path.basename(tfname)
        for pattern, entry in game.search([basename]):
            with entry.open('rb') as f, io.BytesIO() as output:
                version = f.read(18)
                num_messages = version[4]
                output.write(version)
                idx = 0
                stopped = False
                while not stopped:
                    for _ in range(num_messages):
                        line = f.read(LINE_SIZE)
                        output.write(line)
                        if not line:
                            stopped = True
                            break
                        line, rest = line.split(b'\0', maxsplit=1)
                        # assert set(rest) == {0}, rest
                        if idx == 2:
                            print(basename, idx, line.decode())
                    idx += 1

                output.seek(
                    len(version) + LANGS[lang_code] * num_messages * LINE_SIZE,
                    io.SEEK_SET,
                )
                for _, _, line in group:
                    enc = line.encode('cp850')
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
    outstream: IO[str],
) -> None:
    with entry.open('rb') as f:
        version = f.read(18)
        num_messages = version[4]
        print(version)
        idx = 0
        stopped = False
        while not stopped:
            for _ in range(num_messages):
                line = f.read(LINE_SIZE)
                if not line:
                    stopped = True
                    break
                line, rest = line.split(b'\0', maxsplit=1)
                assert set(rest) == {0} or set(rest) == {0, ord(' ')}, rest
                if idx == LANGS['ANG']:  # English
                    print(
                        entry.name,
                        idx,
                        line.decode(errors='ignore'),
                        sep='\t',
                        file=outstream,
                    )
            idx += 1
        assert not f.read()
