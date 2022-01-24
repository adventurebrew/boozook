import sys
import io
import glob
import os
import glob

from read_tot import read_tot, read_uin16le, fix_value

def reads_uin16le(stream):
    return int.from_bytes(stream.read(2), byteorder='little', signed=False)

def reads_uin32le(stream):
    return int.from_bytes(stream.read(4), byteorder='little', signed=False)

def parse_text(text):
    # print(text)
    skip = 0
    parse_six = False
    parse_ten = False
    for c in text:
        if skip > 0:
            skip -= 1
            continue
        if c == 1:
            break
        if c in (2, 5):
            skip = 4
            yield ord(b'\n')
            continue
        if c == 3:
            skip = 1
            continue
        if c == 3 or c == 4:
            skip = 1
            continue
        if c == 6:
            parse_six = True
            continue
        if parse_six:
            if c & 0x80:
                skip = 2
            if c & 0x40:
                skip = 8
            parse_six = False
            continue
        if c in (7, 8, 9):
            continue
        if c == 10:
            parse_ten = True
            continue
        if parse_ten:
            skip = 2 * c
            parse_ten = False
            continue
        if c >= 0x80:
            yield c
            continue
        if c == 186:
            raise NotImplementedError('Oy')
        yield c


def parse_text_data(data):
    with io.BytesIO(data) as stream:
        items_count = reads_uin16le(stream) & 0x3FFF
        # print(items_count)
        index = [(reads_uin16le(stream), reads_uin16le(stream)) for i in range(items_count)]

        # print(index)
        for offset, size in index:
            if offset == 0xFFFF or size == 0:
                yield offset, size, b''
                continue
            assert stream.tell() in dict(index) or stream.tell() == len(data), (stream.tell(), index, len(data))
            stream.seek(offset)
            line_data = stream.read(size)
            yield offset, size, line_data

def extract_texts(out, basename, texts):
    for idx, (offset, size, line_data) in texts.items():
        if line_data:
            # TODO read and replace line
            out.write(basename + '\t"' + bytes(parse_text(line_data[18:])).decode('cp850').replace('"', '`') + '"\n')


if __name__ == '__main__':

    if not len(sys.argv) > 2:
        print('Usage: read_tot.py FILENAME LANG_CODE')
        exit(1)
    filenames = sys.argv[1]
    lang_code = sys.argv[2]

    filenames = glob.iglob(sys.argv[1])
    with open('output.txt', 'w', encoding='utf-8') as out:
        for fname in filenames:
            texts_data = None
            with open(fname, 'rb') as tot_file:
                texts_data, res_data = read_tot(tot_file)

            try:
                if not texts_data:
                    with open(f'{fname[:-4]}.{lang_code}', 'rb') as loc_file:
                        texts_data = loc_file.read()
                # else:
                #     raise ValueError('Oyy')
            except:
                pass

            if texts_data:
                texts = dict(enumerate(parse_text_data(texts_data)))
                extract_texts(out, os.path.basename(fname), texts)
