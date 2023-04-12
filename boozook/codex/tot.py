import io
import operator
import os
from itertools import groupby
from typing import IO, Iterable, Sequence
from boozook.archive import GameBase
from boozook.codex.replace_tot import extract_texts, replace_texts, save_lang_file
from boozook.totfile import fix_value, parse_text_data, read_tot, read_uint32le

from pakal.archive import ArchivePath


def compose(
    game: GameBase,
    lines: Iterable[Sequence[str]],
    lang_code: str = 'ISR',
    encoding: str = 'cp862',
) -> None:
    grouped = groupby(lines, key=operator.itemgetter(0))
    for tfname, group in grouped:
        basename = os.path.basename(tfname)
        for pattern, entry in game.search([basename]):
            source, texts, texts_data = get_original_texts(game, entry)
            texts = dict(enumerate(replace_texts(group, texts)))
            assert texts
            with io.BytesIO() as lang_out:
                save_lang_file(lang_out, texts)
                new_texts_data = lang_out.getvalue()
            print(source)
            # assert texts_data == new_texts_data, (texts_data, new_texts_data)
            if source.name != entry.name:
                game.patch(
                    source.name,
                    new_texts_data,
                    f'{source.stem}.{lang_code}',
                )
            else:
                orig_tot = bytearray(entry.read_bytes())
                orig_tot = orig_tot.replace(texts_data, new_texts_data)
                resoff = fix_value(read_uint32le(orig_tot[52:]), 0xFFFFFFFF, 0)
                if resoff != 0:
                    orig_tot[52:56] = (
                        resoff + len(new_texts_data) - len(texts_data)
                    ).to_bytes(4, byteorder='little', signed=False)
                game.patch(source.name, bytes(orig_tot))
            break
        else:
            raise ValueError(f'entry {basename} was not found')


def get_original_texts(
    game: GameBase,
    entry: ArchivePath,
):
    with entry.open('rb') as stream:
        _, _, texts_data, res_data = read_tot(stream)
    source = entry.name
    if not texts_data:
        lang_patterns = [f'{entry.stem}.{ext}' for ext in ('ANG', 'ISR', 'DAT', 'ALL')]
        for pattern, lang_file in game.search(lang_patterns):
            texts_data = lang_file.read_bytes()
            source = lang_file
            break
        else:
            # Lang file was not found, skip TOT entry
            matches = list(y.name for x, y in game.search([f'{entry.stem}.*']))
            print(f'no text data, please consider looking at: {matches}')
            return source, None, texts_data

    return source, dict(enumerate(parse_text_data(texts_data))), texts_data


def write_parsed(
    game: GameBase,
    entry: ArchivePath,
    outstream: IO[str],
) -> None:
    source, texts, _ = get_original_texts(game, entry)
    if not texts:
        return
    extract_texts(outstream, entry.name, source, texts)
