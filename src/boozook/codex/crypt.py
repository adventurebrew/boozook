from dataclasses import asdict, dataclass
from typing import Mapping

from boozook.codex.stk import replace_many


@dataclass
class CodePageEncoder:
    encoding: str
    errors: str = 'strict'

    def decode(self, text: bytes) -> str:
        return text.decode(**asdict(self))

    def encode(self, text: str) -> bytes:
        return text.encode(**asdict(self))


@dataclass
class KeyReplacer:
    codepage: CodePageEncoder
    mapping: Mapping[str, str]

    def decode(self, text: bytes) -> str:
        return replace_many(self.codepage.decode(text), *self.mapping.items())

    def encode(self, text: str) -> bytes:
        return self.codepage.encode(
            replace_many(
                text,
                *((v, k) for k, v in self.mapping.items()),
            )
        )


HebrewKeyReplacer = KeyReplacer(
    CodePageEncoder('cp862'),
    {
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
    },
)


def decrypt(crypts, texts, lang):
    line = texts.get(lang, None)
    if line is None:
        return '---'
    return crypts[lang].decode(line)


def encrypt(crypts, texts, lang):
    line = texts.get(lang, None)
    if line is None or line == '---':
        return None
    return crypts[lang].encode(line)
