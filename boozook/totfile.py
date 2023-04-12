import io


def read_uint16le(buffer):
    return int.from_bytes(buffer[:2], byteorder='little', signed=False)


def read_uint32le(buffer):
    return int.from_bytes(buffer[:4], byteorder='little', signed=False)


def reads_uint16le(stream):
    return int.from_bytes(stream.read(2), byteorder='little', signed=False)


def reads_uint32le(stream):
    return int.from_bytes(stream.read(4), byteorder='little', signed=False)


def fix_value(original, target, fix):
    return original if original != target else fix


def read_tot(stream):
    header = stream.read(128)
    _version = header[39:42].decode()
    # print(float(_version))

    _variables_count = read_uint32le(header[44:])
    text_offset = fix_value(read_uint32le(header[48:]), 0xFFFFFFFF, 0)
    resources_offset = fix_value(read_uint32le(header[52:]), 0xFFFFFFFF, 0)
    _anim_data_size = read_uint32le(header[56:])
    _im_file_number, _ex_file_number, _commun_handling = [int(x) for x in header[59:62]]

    # print(
    #   _variables_count,
    #   text_offset,
    #   resources_offset,
    #   _anim_data_size,
    #   _im_file_number,
    #   _ex_file_number,
    #   _commun_handling
    # )

    functions = [read_uint16le(header[100 + 2 * i :]) for i in range(14)]
    stream.seek(0, 2)
    file_size = stream.tell()

    offsets = [x for x in (text_offset, resources_offset) if x > 0]
    script_end = min(file_size, file_size, *offsets)

    # print(functions)
    # print(script_end)
    after_size = file_size - max(0, 0, *offsets)
    before_size = max(0, 0, *offsets) - min(file_size, file_size, *offsets)

    text_size, resource_size = (
        (after_size, before_size)
        if text_offset > resources_offset
        else (before_size, after_size)
    )

    stream.seek(128, 0)
    script = stream.read(script_end - 128)
    assert not (128 <= text_offset < script_end)
    assert not (128 <= resources_offset < script_end)
    texts = None
    resources = None

    if text_offset != 0:
        assert stream.tell() == text_offset, (stream.tell(), text_offset)
        stream.seek(text_offset, 0)
        texts = stream.read(text_size)
    if resources_offset != 0:
        assert stream.tell() == resources_offset, (stream.tell(), resources_offset)
        stream.seek(resources_offset, 0)
        resources = stream.read(resource_size)
        assert stream.read() == b''

    # print(texts, resources)
    return script, functions, texts, resources


def parse_text_data(data):
    with io.BytesIO(data) as stream:
        items_count = reads_uint16le(stream)
        # assert items_count == items_count & 0x3FFF  # assertion breaks with woodruff
        items_count &= 0x3FF
        # print(items_count)
        index = [
            (reads_uint16le(stream), reads_uint16le(stream)) for i in range(items_count)
        ]

        # print(index)
        for offset, size in index:
            if offset == 0xFFFF or size == 0:
                yield offset, size, b''
                continue
            # assert stream.tell() in dict(index) or stream.tell() == len(data), (stream.tell(), index, len(data))
            stream.seek(offset)
            line_data = stream.read(size)
            yield offset, size, line_data
