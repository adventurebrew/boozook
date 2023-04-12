import csv
import os
from pathlib import Path

from boozook.codex import cat, tot
from boozook import archive


TEXT_PATTERNS = {
    '*.TOT': ('tot', tot.write_parsed, tot.compose),
    '*.CAT': ('cat', cat.write_parsed, cat.compose),
}


def decode(game, patterns, texts_dir):
    open_files = set()
    for pattern, entry in game.search(patterns):
        agg_file, parse, _ = patterns[pattern]
        text_file = texts_dir / (agg_file + '.tsv')
        mode = 'a' if agg_file in open_files else 'w'
        with open(text_file, mode, encoding='utf-8') as out:
            open_files.add(agg_file)
            parse(game, entry, out)


def encode(game, patterns, texts_dir):
    encoders = set((name, composer) for _, (name, _, composer) in patterns.items())
    for agg_file, composer in encoders:
        text_file = texts_dir / (agg_file + '.tsv')
        if not text_file.exists():
            continue
        with open(text_file, 'r', encoding='utf-8') as text_stream:
            tsv_reader = csv.reader(text_stream, delimiter='\t')
            composer(game, tsv_reader)
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
