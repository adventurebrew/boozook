from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator, Sequence
import csv
import os
from pathlib import Path

from pakal.archive import ArchivePath

from boozook.codex import cat, tot
from boozook import archive
from boozook.codex.crypt import CodePageEncoder, HebrewKeyReplacer, TextEncoder, decrypt, encrypt


LANGS = ['INT'] + [lang.name for lang in cat.Language]

Decoder = Callable[[archive.GameBase, ArchivePath], Iterator[dict[str, bytes | None]]]
Encoder = Callable[[archive.GameBase, Iterable[tuple[str, dict[str, bytes | None]]]], None]

TEXT_PATTERNS: dict[str, tuple[str, Decoder, Encoder]] = {
    '*.TOT': ('tot', tot.write_parsed, tot.compose),
    '*.CAT': ('cat', cat.write_parsed, cat.compose),
}


def encrypt_texts(
    crypts: dict[str, TextEncoder], lines: Iterable[dict[str, str | None]]
) -> Iterator[tuple[str, dict[str, bytes | None]]]:
    for line in lines:
        fname = line.pop('FILE')
        assert fname is not None
        text: dict[str, bytes | None] = {}
        for lang in line.keys():
            text[lang] = encrypt(crypts, line, lang)
        yield fname, text


def escape_quotes(text: str) -> str:
    assert '""' not in text, text
    return text.replace('"', '""')


def decode(
    game: archive.GameBase,
    patterns: dict[str, tuple[str, Decoder, Encoder]],
    texts_dir: Path,
    crypts: dict[str, TextEncoder],
) -> None:
    open_files = set()
    for pattern, entry in game.search(patterns):
        agg_file, parse, _ = patterns[pattern]
        text_file = texts_dir / (agg_file + '.tsv')
        mode = 'a' if agg_file in open_files else 'w'
        with open(text_file, mode, encoding='utf-8') as out:
            if mode == 'w':
                print('FILE', *LANGS, sep='\t', file=out,)
            open_files.add(agg_file)
            for texts in parse(game, entry):
                print(entry.name,*(f'"{escape_quotes(decrypt(crypts, texts, lang))}"' for lang in LANGS), sep='\t', file=out,)


def encode(
    game: archive.GameBase,
    patterns: dict[str, tuple[str, Decoder, Encoder]],
    texts_dir: Path,
    crypts: dict[str, TextEncoder],
) -> None:
    encoders = set((name, composer) for _, (name, _, composer) in patterns.items())
    for agg_file, composer in encoders:
        text_file = texts_dir / (agg_file + '.tsv')
        if not text_file.exists():
            continue
        with open(text_file, 'r', encoding='utf-8') as text_stream:
            tsv_reader = csv.DictReader(text_stream, delimiter='\t')
            composer(game, encrypt_texts(crypts, tsv_reader))
    game.rebuild()


def menu():
    import argparse

    parser = argparse.ArgumentParser(description='Extract Text from Archive')
    parser.add_argument('directory', help='Game directory to work on')
    parser.add_argument(
        '--rebuild',
        '-r',
        action='store_true',
        help='Create modified game resource with the changes',
    )
    parser.add_argument(
        '--allowed',
        '-i',
        action='append',
        help='Allow only specific patterns to be modified',
    )
    parser.add_argument(
        '--keys',
        '-k',
        action='store_true',
        help='Replace Text by Keyboard key position',
    )
    return parser.parse_args()


def main(gamedir: str, rebuild: bool, allowed: Sequence[str]=(), keys: bool = False) -> None:
    patterns = TEXT_PATTERNS

    texts_dir = Path('texts')
    os.makedirs(texts_dir, exist_ok=True)

    decoders: dict[str, TextEncoder] = defaultdict(lambda: CodePageEncoder('cp850'))
    decoders['ISR'] = CodePageEncoder('windows-1255')
    decoders['KOR'] = CodePageEncoder('utf-8', errors='surrogateescape')

    if keys:
        decoders['ISR'] = HebrewKeyReplacer

    game = archive.open_game(gamedir, allowed_patches=allowed or ())
    if not rebuild:
        decode(game, patterns, texts_dir, decoders)
        print('Text extracted\n')
    else:
        encode(game, patterns, texts_dir, decoders)
        print('Text rebuilt\n')


if __name__ == '__main__':
    args = menu()

    main(args.directory, args.rebuild, allowed=args.allowed, keys=args.keys)
