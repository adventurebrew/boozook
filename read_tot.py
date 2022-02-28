import io


def read_uin16le(f):
    return int.from_bytes(f[:2], byteorder='little', signed=False)

def read_uin32le(f):
    return int.from_bytes(f[:4], byteorder='little', signed=False)

def reads_uin16le(stream):
    return int.from_bytes(stream.read(2), byteorder='little', signed=False)

def reads_uin32le(stream):
    return int.from_bytes(stream.read(4), byteorder='little', signed=False)

def fix_value(original, target, fix):
    return original if original != target else fix

qwerty = {
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
    '/': '.'
}

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
        assert f.read() == b''

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
