import csv
import os
from pathlib import Path

from boozook.codex import cat, tot
from boozook import archive


LANGS = ['INT'] + [lang.name for lang in cat.Language]

TEXT_PATTERNS = {
    '*.TOT': ('tot', tot.write_parsed, tot.compose),
    '*.CAT': ('cat', cat.write_parsed, cat.compose),
}


qwerty = {
    't': 'א',
    'c': 'ב',
    'd': 'ג',
    's': 'ד',
    'v': 'ה',
    'u': 'ו',
    'z': 'ז',
    'j': 'ח',
    'y': 'ט',
    'h': 'י',
    'l': 'ך',
    'f': 'כ',
    'k': 'ל',
    'o': 'ם',
    'n': 'מ',
    'i': 'ן',
    'b': 'נ',
    'x': 'ס',
    'g': 'ע',
    ';': 'ף',
    'p': 'פ',
    '.': 'ץ',
    'm': 'צ',
    'e': 'ק',
    'r': 'ר',
    'a': 'ש',
    ',': 'ת',
    '\'': ',',
    '/': '.',
    'w': "'",
}


def decrypt(texts, lang):
    line = texts.get(lang, None)
    if line is None:
        return '---'
    if lang == 'ISR':
        # return replace_many(line.decode('cp862'), *qwerty.items())  # Gobliiins 3
        return line.decode('windows-1255')
    if lang == 'KOR':
        return line.decode('utf-8', errors='surrogateescape')
    return line.decode('cp850')


def encrypt(texts, lang):
    line = texts.get(lang, None)
    if line is None or line == '---':
        return None
    if lang == 'ISR':
        return line.encode('windows-1255')
    if lang == 'KOR':
        return line.encode('utf-8', errors='surrogateescape')
    return line.encode('cp850')


def encrypt_texts(lines):
    for line in lines:
        text = {'FILE': line.pop('FILE')}
        for lang in line.keys():
            text[lang] = encrypt(line, lang)
        yield text


def decode(game, patterns, texts_dir):
    open_files = set()
    for pattern, entry in game.search(patterns):
        agg_file, parse, _ = patterns[pattern]
        text_file = texts_dir / (agg_file + '.tsv')
        mode = 'a' if agg_file in open_files else 'w'
        with open(text_file, mode, encoding='utf-8') as out:
            if mode == 'w':
                print(
                    'FILE',
                    *LANGS,
                    sep='\t',
                    file=out,
                )
            open_files.add(agg_file)
            for texts in parse(game, entry):
                print(
                    entry.name,
                    *(f'"{decrypt(texts, lang)}"' for lang in LANGS),
                    sep='\t',
                    file=out,
                )


def encode(game, patterns, texts_dir):
    encoders = set((name, composer) for _, (name, _, composer) in patterns.items())
    for agg_file, composer in encoders:
        text_file = texts_dir / (agg_file + '.tsv')
        if not text_file.exists():
            continue
        with open(text_file, 'r', encoding='utf-8') as text_stream:
            tsv_reader = csv.DictReader(text_stream, delimiter='\t')
            composer(game, encrypt_texts(tsv_reader))
    game.rebuild()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='extract pak archive')
    parser.add_argument('directory', help='game directory to work on')
    parser.add_argument(
        '--rebuild',
        '-r',
        action='store_true',
        help='create modifed game resource with the changes',
    )
    args = parser.parse_args()

    patterns = TEXT_PATTERNS

    texts_dir = Path('texts')
    os.makedirs(texts_dir, exist_ok=True)

    game = archive.open_game(args.directory)
    if not args.rebuild:
        decode(game, patterns, texts_dir)
    else:
        encode(game, patterns, texts_dir)
