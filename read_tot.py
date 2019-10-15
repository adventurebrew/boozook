import sys
import glob
import os
import numpy as np
import glob

def read_uin16le(f):
    return int.from_bytes(f[:2], byteorder='little', signed=False)

def read_uin32le(f):
    return int.from_bytes(f[:4], byteorder='little', signed=False)

def fix_value(original, target, fix):
    return original if original != target else fix

def read_tot(f):
    header = f.read(128)
    version = header[39:42].decode()
    # print(float(version))

    variables_count = read_uin32le(header[44:])
    text_offset = fix_value(read_uin32le(header[48:]), 0xFFFFFFFF, 0)
    resources_offset = fix_value(read_uin32le(header[52:]), 0xFFFFFFFF, 0)
    anim_data_size = read_uin32le(header[56:])
    im_file_number, ex_file_number, commun_handling = [int(x) for x in header[59:62]]

    # print(variables_count, text_offset, resources_offset, anim_data_size, im_file_number, ex_file_number, commun_handling)


    functions = [read_uin16le(header[100 + 2 * i:]) for i in range(14)]
    f.seek(0, 2)
    file_size = f.tell()

    offsets = [x for x in (text_offset, resources_offset) if x > 0]
    script_end = min(file_size, file_size, *offsets)

    # print(functions)
    # print(script_end)
    after_size = file_size - max(0, 0, *offsets)
    before_size = max(0, 0, *offsets) - min(file_size, file_size, *offsets)

    text_size, resource_size = (after_size, before_size) if text_offset > resources_offset else (before_size, after_size)

    # f.seek(128, 0)
    # script = f.read(script_end - 128)
    texts = None
    resources = None
    if text_offset != 0:
        f.seek(text_offset, 0)
        texts = f.read(text_size)
    if resources_offset != 0:
        f.seek(resources_offset, 0)
        resources = f.read(resource_size)

    # print(texts, resources)
    return texts, resources

def parse_text(text):
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

if __name__ == '__main__':

    if not len(sys.argv) > 2:
        print('Usage: read_tot.py FILENAME LANG_CODE')
        exit(1)
    filenames = sys.argv[1]
    lang_code = sys.argv[2]

    filenames = glob.iglob(sys.argv[1])
    with open('output.txt', 'w', encoding='utf-8') as out:
        for fname in filenames:
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
                items_count = read_uin16le(texts_data) & 0x3FFF
                # print(items_count)
                index = [[read_uin16le(texts_data[2 + i * 4:]), read_uin16le(texts_data[4 + i * 4:])] for i in range(items_count)]
                index = [(offset, size) for offset, size in index if offset != 0xFFFF and size != 0]
                # print(index)
                for offset, size in index:
                    line = texts_data[offset:offset+size]
                    out.write(os.path.basename(fname) + '\t"' + bytes(parse_text(line[18:])).decode('cp850').replace('"', '`') + '"\n')

        # if res_data:
        #     print(res_data)

        # if texts_data:
        #     items_count = read_uin16le(texts_data) & 0x3FFF
        #     print(items_count)
        #     index = [[read_uin16le(texts_data[2 + i * 4:]), read_uin16le(texts_data[4 + i * 4:])] for i in range(items_count)]
        #     index = [(offset, size) for offset, size in index if offset != 0xFFFF and size != 0]
        #     print(index)
        #     with open(f'{fname[:-4]}.{lang_code}', 'rb') as loc_file:
        #         for offset, size in index:
        #             loc_file.seek(offset, 0)
        #             line = loc_file.read(size)
        #             print(line)
        #             break

