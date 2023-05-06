from collections import defaultdict
import csv
import os
from pathlib import Path

from boozook.codex import cat, tot
from boozook import archive
from boozook.codex.crypt import CodePageEncoder, HebrewKeyReplacer, decrypt, encrypt


LANGS = ['INT'] + [lang.name for lang in cat.Language]

TEXT_PATTERNS = {
    '*.TOT': ('tot', tot.write_parsed, tot.compose),
    '*.CAT': ('cat', cat.write_parsed, cat.compose),
}


def encrypt_texts(crypts, lines):
    for line in lines:
        text = {'FILE': line.pop('FILE')}
        for lang in line.keys():
            text[lang] = encrypt(crypts, line, lang)
        yield text


def escape_quotes(text):
    assert '""' not in text, text
    return text.replace('"', '""')


def decode(game, patterns, texts_dir, crypts):
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
                    *(
                        f'"{escape_quotes(decrypt(crypts, texts, lang))}"'
                        for lang in LANGS
                    ),
                    sep='\t',
                    file=out,
                )


def encode(game, patterns, texts_dir, crypts):
    encoders = set((name, composer) for _, (name, _, composer) in patterns.items())
    for agg_file, composer in encoders:
        text_file = texts_dir / (agg_file + '.tsv')
        if not text_file.exists():
            continue
        with open(text_file, 'r', encoding='utf-8') as text_stream:
            tsv_reader = csv.DictReader(text_stream, delimiter='\t')
            composer(game, encrypt_texts(crypts, tsv_reader))
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
    parser.add_argument(
        '--allowed',
        '-i',
        action='append',
        help='allow only specific patterns to be modified',
    )
    parser.add_argument(
        '--keys',
        '-k',
        action='store_true',
        help='replace text by keyboard key position',
    )
    args = parser.parse_args()

    patterns = TEXT_PATTERNS

    texts_dir = Path('texts')
    os.makedirs(texts_dir, exist_ok=True)

    decoders = defaultdict(lambda: CodePageEncoder('cp850'))
    decoders['ISR'] = CodePageEncoder('windows-1255')
    decoders['KOR'] = CodePageEncoder('utf-8', errors='surrogateescape')

    if args.keys:
        decoders['ISR'] = HebrewKeyReplacer

    game = archive.open_game(args.directory, allowed_patches=args.allowed or ())
    if not args.rebuild:
        decode(game, patterns, texts_dir, decoders)
    else:
        encode(game, patterns, texts_dir, decoders)
