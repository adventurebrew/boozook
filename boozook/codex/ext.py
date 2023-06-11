import io
import itertools
from pathlib import Path

import numpy as np
from PIL import Image

from boozook.archive import GameBase

from pakal.archive import ArchivePath
from boozook.codex.stk import unpack_chunk
from boozook.codex.stk_compress import pack_content
from boozook.grid import convert_to_pil_image

from boozook.totfile import read_tot, reads_uint32le


def read_sint16le(f):
    return int.from_bytes(f[:2], byteorder='little', signed=True)


def read_uint16le(f):
    return int.from_bytes(f[:2], byteorder='little', signed=False)


def read_uint32le(f):
    return int.from_bytes(f[:4], byteorder='little', signed=False)


def read_sint32le(f):
    return int.from_bytes(f[:4], byteorder='little', signed=True)


def pack_sprite(data):
    groups = [(v, list(g)) for v, g in itertools.groupby(data)]
    out = bytearray()
    for v, group in groups:
        while len(group) > 2048:
            repeat = 2047
            out += bytes([v << 4 | (repeat >> 8) & 7, repeat & 0xFF])
            group = group[2048:]
            # print('DEC', v, repeat + 1)
        repeat = len(group) - 1
        # print('DEC', v, repeat + 1)
        # v &= 0x0F
        assert v <= 0x0F, v
        if repeat > 7:
            out += bytes([v << 4 | (repeat >> 8) & 7, repeat & 0xFF])
        else:
            out += bytes([v << 4 | 8 | repeat])
    return bytes(out)


def unpack_sprite(data, width, height):
    out = bytearray()
    with io.BytesIO(data) as stream:
        while len(out) < width * height:
            val = stream.read(1)[0]
            repeat = val & 7
            val &= 0xF8

            if not val & 8:
                repeat <<= 8
                repeat %= 4096 * 4096
                repeat |= stream.read(1)[0]
                assert repeat > 7, repeat
            else:
                assert repeat <= 7, repeat
            repeat += 1
            val >>= 4

            out += bytes([val for _ in range(repeat)])
            # print('DEC', val, len(out), repeat)
        assert len(out) == width * height, (len(out), width, height)
        res = list(out)
        if res:
            enc = pack_sprite(res)
            assert enc == data, (enc, data)
        return res


def uncompress_sprite(data, width, height):
    with io.BytesIO(data) as stream:
        codec = stream.read(1)[0]
        if codec != 1:
            raise NotImplementedError(codec)

        uncompressed_size = reads_uint32le(stream)
        assert uncompressed_size == width * height
        return list(unpack_chunk(stream, uncompressed_size))


# def uncompress_sprite(data, width, height):
#     with io.BytesIO(data) as stream:
#         codec = stream.read(1)[0]
#         if codec != 1:
#             raise NotImplementedError(codec)

#         buffer = [0 for _ in range(4370)]
#         src_left = read_uint32le(stream.read(4))

#         buf_pos = 4096 - 18
#         pos = 0

#         buffer[:buf_pos] = [32 for _ in range(buf_pos)]

#         im_buffer = [0 for _ in range(width * height)]

#         cmd_vars = []
#         while pos < width * height:
#             assert src_left > 0

#             if not cmd_vars:
#                 cmd_vars = list(int(x) for x in f'{stream.read(1)[0]:08b}')
#                 # print(cmd_vars)

#             cmd_var = cmd_vars.pop()

#             print('CMD_VAR', cmd_var)
#             if cmd_var == 1:
#                 # write next byte to buffer and image
#                 im_buffer[pos] = buffer[buf_pos] = stream.read(1)[0]
#                 pos += 1
#                 buf_pos = (buf_pos + 1) % 4096
#             else:
#                 offset = stream.read(1)[0]
#                 temp = stream.read(1)[0]

#                 print('OFFSET', offset, 'TEMP', temp)

#                 offset |= (temp & 0xF0) << 4
#                 offset %= 4096
#                 str_len = (temp & 0x0F) + 3

#                 print('OFFSET', offset, 'STR_LEN', str_len)

#                 for counter in range(str_len):
#                     im_buffer[pos] = buffer[buf_pos] = buffer[(offset + counter) % 4096]
#                     pos += 1
#                     buf_pos = (buf_pos + 1) % 4096

#                 assert str_len < src_left, (str_len, src_left)

#             src_left -= 1
#         assert (cmd_vars == [] or set(cmd_vars) == {0}) and len(cmd_vars) < 8, cmd_vars
#         assert stream.read() == b''
#         return im_buffer

# PALETTE = [((53 + x) ** 2 * 13 // 5) % 256 for x in range(256 * 3)]

PALETTE = list(
    itertools.chain(
        (0x00, 0x00, 0x00),
        (0x00, 0x00, 0x2A),
        (0x00, 0x2A, 0x00),
        (0x00, 0x2A, 0x2A),
        (0x2A, 0x00, 0x00),
        (0x2A, 0x00, 0x2A),
        (0x2A, 0x15, 0x00),
        (0x2A, 0x2A, 0x2A),
        (0x15, 0x15, 0x15),
        (0x15, 0x15, 0x3F),
        (0x15, 0x3F, 0x15),
        (0x15, 0x3F, 0x3F),
        (0x3F, 0x15, 0x15),
        (0x3F, 0x15, 0x3F),
        (0x3F, 0x3F, 0x15),
        (0x3F, 0x3F, 0x3F),
    )
)
PALETTE = PALETTE * 16
assert len(PALETTE) == 0x300
# palette = [x << 2 for x in palette]
PALETTE = [(x << 2) % 256 for x in PALETTE]


def read_ext_table(stream):
    items_count = read_sint16le(stream.read(2))
    unknown = stream.read(1)[0]
    assert items_count > 0, items_count

    for i in range(items_count):
        offset = read_sint32le(stream.read(4))
        size = read_uint16le(stream.read(2))
        width = read_uint16le(stream.read(2))
        height = read_uint16le(stream.read(2))
        packed = width & 0x8000 != 0
        width &= 0x7FFF
        yield (offset, size, width, height, packed)


def parse(game: GameBase, entry: ArchivePath, target: str | Path):
    target = Path(target)
    reses = {}
    with entry.open('rb') as f:
        _, _, _, res_data = read_tot(f)
    if res_data:
        reses['TOT'] = res_data

    for ext_pattern, ext_entry in game.search([entry.with_suffix('.EXT').name]):
        res_data = ext_entry.read_bytes()
        reses['EXT'] = res_data

    com_data = {}
    for com_pattern, com_entry in game.search(['COMMUN.EX*']):
        com_data[com_entry.name] = com_entry.read_bytes()

    bim = None
    palette = list(PALETTE)
    for ext, res_data in reses.items():
        with io.BytesIO(res_data) as f:
            items = list(read_ext_table(f))
            table_off = f.tell()
            for idx, (offset, size, width, height, packed) in enumerate(items):
                if offset < 0:
                    print('NEGATIVE OFFSET')
                    if ext == 'TOT':
                        raise ValueError('IM resource not implemented')
                    # TODO: handle different COMMUN.EX file for different TOTs
                    with io.BytesIO(com_data[com_entry.name]) as stream:
                        assert ~offset == -(offset + 1)
                        stream.seek(~offset)
                        if packed:
                            uncompressed_size = reads_uint32le(stream)
                            data = unpack_chunk(stream, uncompressed_size)
                        else:
                            data = stream.read(size)
                else:
                    assert f.tell() == offset + table_off, (
                        f.tell(),
                        offset + table_off,
                    )
                    if packed:
                        if ext == 'TOT':
                            continue
                        uncompressed_size = reads_uint32le(f)
                        data = unpack_chunk(f, uncompressed_size)
                    else:
                        data = f.read(size)
                if data[:2] == b'\x01\x02':
                    print('UNCOMPRESS', entry.name, idx)
                    im = uncompress_sprite(data[2:], width, height)
                else:
                    print('UNPACK', entry.name, idx)
                    im = unpack_sprite(data, width, height)

                image_path = target / f'{entry.stem}.{ext}_{idx}.png'
                if width & height:
                    bim = convert_to_pil_image(im, size=(width, height))
                    bim.putpalette(palette)
                    bim.save(image_path)
                    print(image_path)
                elif len(data) == 768:
                    print('PALETTE', entry.name, idx)
                    palette = [(x << 2) % 256 for x in data]
                    if bim:
                        bim.putpalette(palette)
                        bim.save(image_path)
                else:
                    print(len(data), len(im))


def compress_sprite(data):
    data = bytes(data)
    out = b'\x01\x02\x01' + pack_content(data)

    size = int.from_bytes(out[3:7], byteorder='little', signed=False)
    reunpacked = bytes(
        uncompress_sprite(
            out[2:],
            size,
            1,
        )
    )
    if data != reunpacked:
        print(data[:100])
        print(reunpacked[:100])
        print(reunpacked[:100] == data[:100])
    assert data == reunpacked

    return bytes(out)


def compose(game: GameBase, entry: ArchivePath, target: str | Path):
    target = Path(target)
    reses = {}
    with entry.open('rb') as f:
        _, _, _, res_data = read_tot(f)
        if res_data:
            reses['TOT'] = res_data

    for ext_pattern, ext_entry in game.search([entry.with_suffix('.EXT').name]):
        res_data = ext_entry.read_bytes()
        reses['EXT'] = res_data

    if not res_data:
        return

    assert res_data

    for ext, res_data in reses.items():

        outfile = bytearray()
        outdata = bytearray()

        if ext == 'TOT':
            with entry.open('rb') as f:
                data = f.read()
            outfile += data.replace(res_data, b'')
            assert outfile + res_data == data

        outfile += res_data[:3]

        with io.BytesIO(res_data) as f:
            items = list(read_ext_table(f))
            table_off = f.tell()

            for idx, (offset, size, width, height, packed) in enumerate(items):
                data = None
                if offset < 0:
                    raise ValueError('commun not supported for inject')
                else:
                    assert f.tell() == offset + table_off, (
                        f.tell(),
                        offset + table_off,
                    )
                    if packed:
                        raise ValueError('packed not yet supported')
                    else:
                        data = f.read(size)

                assert data is not None
                offset = len(outdata)
                inject_pic = target / f'{entry.stem}.{ext}_{idx}.png'
                if not inject_pic.exists() or not width & height:
                    outdata += data
                    outfile += b''.join(
                        [
                            offset.to_bytes(4, byteorder='little', signed=False),
                            len(data).to_bytes(2, byteorder='little', signed=False),
                            width.to_bytes(2, byteorder='little', signed=False),
                            height.to_bytes(2, byteorder='little', signed=False),
                        ]
                    )
                    continue

                im_data = np.asarray(Image.open(inject_pic)).ravel()
                im_type = None

                if data[:2] == b'\x01\x02':
                    im_type = 'UNCOMPRESS'
                    print(im_type, entry.name, idx)
                    im = uncompress_sprite(data[2:], width, height)

                else:
                    im_type = 'UNPACK'
                    print(im_type, entry.name, idx)
                    im = unpack_sprite(data, width, height)

                print(ext, inject_pic, width, height)

                if not np.array_equal(im, im_data):
                    if len(im_data) != width * height:
                        raise ValueError(len(im_data), width * height)
                    data = {
                        'UNCOMPRESS': compress_sprite,
                        'UNPACK': pack_sprite,
                    }[im_type](im_data)

                outdata += data
                outfile += b''.join(
                    [
                        offset.to_bytes(4, byteorder='little', signed=False),
                        len(data).to_bytes(2, byteorder='little', signed=False),
                        width.to_bytes(2, byteorder='little', signed=False),
                        height.to_bytes(2, byteorder='little', signed=False),
                    ]
                )

        game.patch(f'{entry.stem}.{ext}', outfile + outdata)

        # outdir = Path('attempt')
        # os.makedirs(outdir, exist_ok=True)
        # with open(outdir / f'{entry.stem}.{ext}', 'wb') as out:
        #     out.write(outfile + outdata)
