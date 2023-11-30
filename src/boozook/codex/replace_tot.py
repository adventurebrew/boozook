from collections import defaultdict
import io
import itertools
import struct
from boozook.codex.base import write_uint16_le

from boozook.codex.stk import replace_many
from boozook.totfile import reads_uint16le


def escape(seq):
    return b''.join(f'\\x{v:02x}'.encode() for v in seq)


def escape_bytes(data):
    with io.BytesIO(data) as stream:
        while True:
            r = stream.read(1)
            if not r:
                break
            c = r[0]
            if c == 1:
                rest = stream.read(1)
                if rest == b'\0':
                    break
                print(len(rest), stream.tell(), stream.tell() % 2)
                print('REST', rest, stream.read())
                yield escape(bytes([c]) + rest)
                continue
            if c in (2, 5):
                xpos, ypos = reads_uint16le(stream), reads_uint16le(stream)
                yield b'\n' if c == 2 else b'\n~~~\n'
                yield f'{xpos}@{ypos}\n'.encode('ascii')
                continue
            if c in (3, 4):
                yield escape(bytes([c]) + stream.read(1))
                continue
            if c == 6:
                a = stream.read(1)[0]
                skip = 0
                if a & 0x80:
                    skip += 2
                elif a & 0x40:
                    skip += 8
                elif a & 0xC0:
                    skip += 10
                yield escape(bytes([c, a]) + stream.read(skip))
                continue
            if c in (7, 8, 9):
                yield escape(bytes([c]))
                continue
            if c == 10:
                a = stream.read(1)[0]
                yield escape(bytes([c, a]) + stream.read(2 * a))
            if c >= 0x80:
                yield bytes([c])
                continue
            if c == 186:
                raise NotImplementedError('Oy')
            yield bytes([c])


text_reps = [('\t', '|~t~|'), ('\r', '|~r~|')]
bin_rep = [(chr(i), f'\\x{i:02x}') for i in itertools.chain(range(10), [18])]


def reencode(text):
    escaped = replace_many(
        text,
        (b'\n~~~\n', b'|~~~|'),
        (b'\n', b'|~$~|'),
        (b'|~r~|', b'\r'),
        (b'|~t~|', b'\t'),
    )
    breaked = b''.join(build_line_breaks(escaped))
    return b''.join(
        encode_seq(i, seq)
        for i, seq in enumerate(
            breaked.split(b'\\x'),
        )
    )


def extract_texts(sources, verify=True):
    text_line_data = defaultdict(dict)
    for lang, texts in sources.items():
        for idx, (offset, size, line_data) in texts.items():
            text_line_data[idx][lang] = None
            if len(line_data) > 18 and line_data[18] not in {0, ord(b'@'), 4}:
                # print('LINEDATA', list(line_data[:18]), line_data[18:])
                escaped = b''.join(escape_bytes(line_data[18:]))
                # TODO read and replace line
                text = replace_many(
                    escaped.decode('utf-8', errors='surrogateescape'),
                    *text_reps,
                    *bin_rep,
                )
                text_line_data[idx][lang] = text.encode(
                    'utf-8',
                    errors='surrogateescape',
                )

                if verify:
                    # when reading tsv file, escaped double quotes are converted
                    escaped = text_line_data[idx][lang]
                    encoded = reencode(escaped)
                    assert line_data[18:].startswith(encoded), (
                        line_data[18:-2],
                        encoded,
                    )

    yield from text_line_data.values()


def build_line_breaks(lines):
    xpos, ypos = 0, 0
    while True:
        two, cont2 = None, lines
        five, cont5 = None, lines
        if b'|~$~|' in lines:
            two, cont2 = lines.split(b'|~$~|', maxsplit=1)
        if b'|~~~|' in lines:
            five, cont5 = lines.split(b'|~~~|', maxsplit=1)

        if two is None and five is None:
            yield lines
            return

        if two is not None and (five is None or len(two) < len(five)):
            yield two + b'\\x02'
            pos, *lines = cont2.split(b'|~$~|', maxsplit=1)
        else:
            assert five is not None
            yield five + b'\\x05'
            pos, *lines = cont5.split(b'|~$~|', maxsplit=1)
        try:
            xpos, ypos = (int(x) for x in pos.split(b'@', maxsplit=1))
        except ValueError:
            # Position is omitted, assume next multiple of 10 for ypos
            xpos, ypos = xpos, ypos + 10
            lines = b'|~$~|'.join([pos, *lines])
        else:
            lines = b'|~$~|'.join([*lines])
        yield write_uint16_le(xpos) + write_uint16_le(ypos)


def replace_texts(lines, texts, lang):
    for (offset, size, line_data), line in zip(texts.values(), lines):
        escaped = line[lang]
        if (
            len(line_data) > 18
            and line_data[18] not in {0, ord(b'@'), 4}
            and escaped is not None
        ):
            encoded = reencode(escaped)
            # assert line_data[18:].startswith(encoded), (line_data[18:-2], encoded)
            line_data = line_data[:18] + encoded + b'\x01\x00'
        yield offset, size, line_data


def encode_seq(i, seq):
    if not i:
        return seq
    try:
        return bytes([int(b'0x' + seq[:2], 16)]) + seq[2:]
    except:
        return seq


def save_lang_file(out, texts):
    uint16le_x2 = struct.Struct('<2H')
    out.write(len(texts).to_bytes(2, byteorder='little', signed=False))
    ordered = sorted(texts.items(), key=lambda t: t[1][0])
    # print('ORDERED', [(idx, offset, size) for idx, (offset, size, _) in ordered])
    edited = {}
    with io.BytesIO() as outstream:
        goff = 2 + 4 * len(texts)
        # print('GOFF', goff)
        for idx, (offset, size, line_data) in ordered:
            if offset not in edited:
                edited[offset] = goff
            if line_data:
                texts[idx] = (goff, len(line_data), line_data)
                outstream.write(line_data)
                goff = edited[offset] + len(line_data)
        for idx, (offset, size, line_data) in texts.items():
            # print('OFFSET', offset, line_data)
            out.write(uint16le_x2.pack(offset, size))
        out.write(outstream.getvalue())
