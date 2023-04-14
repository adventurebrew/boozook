import io
import itertools
from pathlib import Path
from boozook.archive import GameBase

from pakal.archive import ArchivePath
from boozook.codex.stk import unpack_chunk
from boozook.grid import convert_to_pil_image

from boozook.totfile import read_tot, reads_uint32le


def read_sint16le(f):
    return int.from_bytes(f[:2], byteorder='little', signed=True)


def read_uint16le(f):
    return int.from_bytes(f[:2], byteorder='little', signed=False)


def read_uint32le(f):
    return int.from_bytes(f[:4], byteorder='little', signed=False)


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


def parse(game: GameBase, entry: ArchivePath, target: str | Path):
    target = Path(target)
    ext = entry.suffix
    if ext == '.EXT':
        res_data = entry.read_bytes()
    elif ext == '.TOT':
        with entry.open('rb') as f:
            _, _, _, res_data = read_tot(f)
        if not res_data:
            return

    assert res_data
    bim = None
    palette = list(PALETTE)
    with io.BytesIO(res_data) as f:
        items_count = read_sint16le(f.read(2))
        unknown = f.read(1)[0]
        assert items_count > 0, items_count

        items = []
        for i in range(items_count):
            offset = read_uint32le(f.read(4))
            size = read_uint16le(f.read(2))
            width = read_uint16le(f.read(2))
            height = read_uint16le(f.read(2))
            packed = width & 0x8000 != 0
            width &= 0x7FFF
            assert not packed
            items.append((offset, size, width, height, packed))

        table_off = f.tell()
        for idx, (offset, size, width, height, packed) in enumerate(items):
            assert f.tell() == offset + table_off, (f.tell(), offset + table_off)
            data = f.read(size)
            if data[:2] == b'\x01\x02':
                print('UNCOMPRESS', entry.name, idx)
                im = uncompress_sprite(data[2:], width, height)
            else:
                print('UNPACK', entry.name, idx)
                im = unpack_sprite(data, width, height)

                if im:
                    enc = pack_sprite(im)
                    assert enc == data, (enc, data)
                    assert unpack_sprite(enc, width, height) == im
            if width & height:
                bim = convert_to_pil_image(im, size=(width, height))
                bim.putpalette(palette)
                bim.save(target / f'{entry.name}_{idx}.png')
                print(target / f'{entry.name}_{idx}.png')
            elif len(data) == 768:
                print('PALETTE', entry.name, idx)
                palette = [(x << 2) % 256 for x in data]
                if bim:
                    bim.putpalette(palette)
                    bim.save(target / f'{entry.name}_{idx}.png')
            else:
                print(len(data), len(im))


def compose(game: GameBase, entry: ArchivePath, target: str | Path):
    pass
