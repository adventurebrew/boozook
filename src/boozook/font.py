import os
from pathlib import Path

from boozook import archive
from boozook.codex import let


FONT_PATTERNS = {
    '*.LET': ('fonts', let.decode_font, let.compose),
    '*.FNT': ('fonts', let.decode_font, let.compose),
}


def decode(game, patterns, fonts_dir):
    for pattern, entry in game.search(patterns):
        _, parse, _ = patterns[pattern]
        parse(game, entry, fonts_dir)


def encode(game, patterns, fonts_dir):
    for pattern, entry in game.search(patterns):
        _, _, compose = patterns[pattern]
        compose(game, entry, fonts_dir)
    game.rebuild()


def menu():
    import argparse

    parser = argparse.ArgumentParser(description='Extract Fonts from Archive')
    parser.add_argument('directory', help='Game directory to work on')
    parser.add_argument(
        '--rebuild',
        '-r',
        action='store_true',
        help='Create modifed game resource with the changes',
    )
    return parser.parse_args()


def main(gamedir, rebuild):
    patterns = FONT_PATTERNS

    fonts_dir = Path('fonts')
    os.makedirs(fonts_dir, exist_ok=True)

    game = archive.open_game(gamedir)
    if not rebuild:
        decode(game, patterns, fonts_dir)
    else:
        encode(game, patterns, fonts_dir)


if __name__ == '__main__':
    args = menu()

    main(args.directory, args.rebuild)
