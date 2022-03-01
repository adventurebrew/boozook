import sys
import io
import glob
import os
import glob
import struct
import binascii

from read_tot import fix_value, read_tot, parse_text, parse_text_data, read_uin32le
from extract import replace_many

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
                rest = stream.read(2)
                print(len(rest), stream.tell(), stream.tell() % 2)
                # assert set(rest) == {0}, rest
                # yield escape(bytes([c]) + rest)
                break
            if c in (2, 5):
                col = escape(bytes([c]) + stream.read(4))
                # values are {c}\x00\x00\x{i*10:02x}\x00 for i = line_number starting from 1
                # count is shared in both (e.g can be \x02\..x0a then \x05\..x14)
                yield b'\n' if c == 2 else b'\n~~~\n'
                continue
            if c in (3, 4):
                yield escape(bytes([c]) + stream.read(1))
                continue
            if c == 6:
                a = stream.read(1)[0]
                skip = 0
                if a & 0x80:
                    skip += 2 
                if a & 0x40:
                    skip += 8 
                yield escape(bytes([a, c]) + stream.read(skip))
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


text_reps = [('"', '`'), ('\t', '|~t~|'), ('\r', '|~r~|')]
bin_rep = [(chr(i), f'\\x{i:02x}') for i in range(10)]

def extract_texts(out, basename, texts):
    for idx, (offset, size, line_data) in texts.items():
        if len(line_data) > 18 and line_data[18] not in {0, ord(b'@'), 4}:
            escaped = b''.join(escape_bytes(line_data[18:]))
            # assert aaa == line_data[18:], (aaa, line_data[18:])
            # TODO read and replace line
            out.write(basename
                + '\t' + binascii.hexlify(line_data[:18]).decode()
                + '\t"' + replace_many(escaped.decode('cp850'), *text_reps, *bin_rep) # , ('\n', '|~$~|'))
                + '"\t"' + replace_many(bytes(parse_text(line_data[18:])).decode('cp850'), *text_reps)
                + '"\n'
            )

def build_line_breaks(lines):
    num = 10
    while True:
        two, cont2 = '', lines
        five, cont5 = '', lines
        if '|~$~|' in lines:
            two, cont2 = lines.split('|~$~|', maxsplit=1)
        if '|~~~|' in lines:
            five, cont5 = lines.split('|~~~|', maxsplit=1)

        if not two and not five:
            yield lines
            return

        if two and (not five or len(two) < len(five)):
            yield two + f'\\x02\\x00\\x00\\x{num:02x}\\x00'
            lines = cont2
        else:
            yield five + f'\\x05\\x00\\x00\\x{num:02x}\\x00'
            lines = cont5
        num += 10
        # two, cont2 = lines.split('|~~~|', maxsplit=1)
        # print(lines + '\n\n')
        # two = lines.find('|~$~|')
        # five = lines.find('|~~~|')
        # if two < 0 and five < 0:
        #     print('DONE', lines)
        #     yield lines
        #     return
        # print(two, five)
        # if two < five or five < 0:
        #     yield lines[:two] + f'\\x02\\x00\\x00\\x{num:02x}\\x00'
        #     print('TWO', lines[:two])
        #     lines = lines[two + 5:]
        # else:
        #     yield lines[:five] + f'\\x05\\x00\\x00\\x{num:02x}\\x00'
        #     print('FIVE', lines[:five])
        #     lines = lines[five + 5:]
        # num += 10


bump_lets = zip(range(ord('א'), ord('ת') + 1), range(ord('@'), ord('Z') + 1))
bump_lets = [(chr(c), chr(r)) for c, r in bump_lets]
# print(bump_lets)
# exit(1)

def replace_texts(lines, texts):
    for offset, size, line_data in texts.values():
        if len(line_data) > 18 and line_data[18] not in {0, ord(b'@'), 4}:
            fname, escaped = next(lines).split('\t')
            text = bytes(parse_text(line_data[18:]))
            breaked = ''.join(build_line_breaks(escaped[:-1]))
            # breaked = replace_many(breaked, *bump_lets)
            encoding = 'windows-1255'  # 'cp862'
            encoded = b''.join(encode_seq(i, seq) for i, seq in enumerate(breaked.encode(encoding, errors='ignore').split(b'\\x')))
            line_data = line_data[:18] + encoded + b'\x01\x00'
        yield offset, size, line_data

def encode_seq(i, seq):
    if not i:
        return seq
    try:
        return bytes([int(b'0x' + seq[:2], 16)]) + seq[2:]
    except:
        return seq

def save_lang_file(out, text_data, texts):
    import pprint
    uint16le_x2 = struct.Struct('<2H')
    out.write(texts_data[:2])
    ordered = sorted(texts.items(), key=lambda t: t[1][0])
    print('ORDERED', [(idx, offset, size) for idx, (offset, size, _) in ordered])
    edited = {}
    with io.BytesIO() as outstream:
        goff = 2 + 4 * len(texts)
        print('GOFF', goff)
        for idx, (offset, size, line_data) in ordered:
            if not offset in edited:
                edited[offset] = goff
            if line_data:
                texts[idx] = (goff, len(line_data), line_data)
                outstream.write(line_data)
                goff = edited[offset] + len(line_data)
        for idx, (offset, size, line_data) in texts.items():
            print('OFFSET', offset, line_data)
            out.write(uint16le_x2.pack(offset, size))
        out.write(outstream.getvalue())

if __name__ == '__main__':

    if not len(sys.argv) > 2:
        print('Usage: read_tot.py FILENAME LANG_CODE')
        exit(1)
    filenames = sys.argv[1]
    lang_code = sys.argv[2]

    filenames = sorted(glob.iglob(sys.argv[1]))
    print(filenames)

    extract = True
    mode = 'w' if extract else 'r'
    lines_file = 'output.txt' if extract else 'input.txt'

    with open(lines_file, mode, encoding='utf-8') as out:
        for fname in filenames:
            texts_data = None
            with open(fname, 'rb') as tot_file:
                _, _, texts_data, res_data = read_tot(tot_file)

            print('FNAME', os.path.basename(fname))

            if texts_data:
                print('INTERNAL', fname)
                texts = dict(enumerate(parse_text_data(texts_data)))
                # write texts
                if extract:
                    extract_texts(out, os.path.basename(fname), texts)
                else:
                    texts = dict(enumerate(replace_texts(out, texts)))
                    with io.BytesIO() as lang_out:
                        save_lang_file(lang_out, texts_data, texts)
                        new_texts_data = lang_out.getvalue()
                    with open(fname, 'rb') as tot_file:
                        orig_tot = bytearray(tot_file.read())
                    orig_tot = orig_tot.replace(texts_data, new_texts_data)
                    resoff = fix_value(read_uin32le(orig_tot[52:]), 0xFFFFFFFF, 0)
                    if resoff != 0:
                        orig_tot[52:56] = (resoff + len(new_texts_data) - len(texts_data)).to_bytes(4, byteorder='little', signed=False)
                    with open(os.path.basename(fname), 'wb') as out_file:
                        out_file.write(orig_tot)
                continue

            try:
                if not texts_data:
                    with open(f'{fname[:-4]}.ANG', 'rb') as loc_file:
                        texts_data = loc_file.read()
                # else:
                #     raise ValueError('Oyy')
            except:
                pass

            if texts_data:
                texts = dict(enumerate(parse_text_data(texts_data)))
                # write texts
                if extract:
                    extract_texts(out, os.path.basename(fname), texts)

                else:
                    # read texts
                    texts = dict(enumerate(replace_texts(out, texts)))

                    # write new lang file
                    with open(f'{os.path.basename(fname)[:-4]}.{lang_code}', 'wb') as lang_out:
                        save_lang_file(lang_out, texts_data, texts)
