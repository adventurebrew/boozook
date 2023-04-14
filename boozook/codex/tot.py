import io
import operator
from itertools import groupby
from pathlib import Path
from typing import Iterable, Sequence
from boozook.archive import GameBase
from boozook.codex.cat import Language
from boozook.codex.replace_tot import extract_texts, replace_texts, save_lang_file
from boozook.totfile import fix_value, parse_text_data, read_tot, read_uint32le

from pakal.archive import ArchivePath


def empty_lang(group, lang):
    return all(line[lang] is None for line in group)


def compose(
    game: GameBase,
    lines: Iterable[Sequence[str]],
) -> None:
    grouped = groupby(lines, key=operator.itemgetter('FILE'))
    for tfname, group in grouped:
        basename = Path(tfname).name
        group = list(group)
        langs = list(group[0].keys())
        langs.remove('FILE')
        for pattern, entry in game.search([basename]):
            texts = get_original_texts(game, entry)
            new_texts = {
                lang: dict(
                    enumerate(
                        replace_texts(iter(group), texts.get(lang, texts['DAT']), lang)
                    )
                )
                for lang in langs
                if not empty_lang(group, lang)
            }

            for lang, lang_text in new_texts.items():
                if lang == 'INT' and 'INT' not in texts:
                    continue
                texts_data = texts.get(lang, texts['DAT'])
                with io.BytesIO() as lang_out:
                    save_lang_file(lang_out, lang_text)
                    new_texts_data = lang_out.getvalue()
                # assert texts_data == lang_text, (texts_data, lang_text)

                parsed = dict(enumerate(parse_text_data(new_texts_data)))
                assert parsed == lang_text, (parsed, lang_text)

                if lang != 'INT':
                    game.patch(
                        (
                            f'{Path(tfname).stem}.{lang}'
                            if lang in texts
                            else f'{Path(tfname).stem}.DAT'
                        ),
                        new_texts_data,
                        f'{Path(tfname).stem}.{lang}',
                    )

                else:
                    orig_tot = bytearray(entry.read_bytes())
                    orig_tot = orig_tot.replace(texts_data, new_texts_data)
                    resoff = fix_value(read_uint32le(orig_tot[52:]), 0xFFFFFFFF, 0)
                    if resoff != 0:
                        orig_tot[52:56] = (
                            resoff + len(new_texts_data) - len(texts_data)
                        ).to_bytes(4, byteorder='little', signed=False)
                    game.patch(basename, bytes(orig_tot))
            break
        else:
            raise ValueError(f'entry {basename} was not found')


def get_original_texts(
    game: GameBase,
    entry: ArchivePath,
):
    sources = {}
    with entry.open('rb') as stream:
        _, _, texts_data, res_data = read_tot(stream)
    if texts_data:
        sources['INT'] = texts_data
    lang_patterns = [f'{entry.stem}.{ext.name}' for ext in Language]
    for pattern, lang_file in game.search(lang_patterns):
        sources[lang_file.suffix[1:]] = lang_file.read_bytes()

    return {
        source: dict(enumerate(parse_text_data(texts_data)))
        for source, texts_data in sources.items()
    }


def write_parsed(
    game: GameBase,
    entry: ArchivePath,
) -> None:
    texts = get_original_texts(game, entry)
    if not texts:
        return
    yield from extract_texts(texts)
