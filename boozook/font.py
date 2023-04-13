import os
from pathlib import Path

from boozook import archive
from boozook.codex import let


FONT_PATTERNS = {
    '*.LET': ('fonts', let.decode_font, let.compose),
}


def decode(game, patterns, fonts_dir):
    for pattern, entry in game.search(patterns):
        _, parse, _ = patterns[pattern]
        parse(game, entry, fonts_dir)


def encode(game, patterns, texts_dir):
    for pattern, entry in game.search(patterns):
        _, _, compose = patterns[pattern]
        compose(game, entry, fonts_dir)
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

    patterns = FONT_PATTERNS

    fonts_dir = Path('fonts')
    os.makedirs(fonts_dir, exist_ok=True)

    game = archive.open_game(args.directory)
    if not args.rebuild:
        decode(game, patterns, fonts_dir)
    else:
        encode(game, patterns, fonts_dir)
