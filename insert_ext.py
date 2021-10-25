import io
import os
import sys
import glob
import itertools

from PIL import Image
import numpy as np

from grid import convert_to_pil_image
from read_tot import read_tot

def read_sint16le(f):
    return int.from_bytes(f[:2], byteorder='little', signed=True)


def read_uint16le(f):
    return int.from_bytes(f[:2], byteorder='little', signed=False)


def read_uint32le(f):
    return int.from_bytes(f[:4], byteorder='little', signed=False)


def uncompress_sprite(data, width, height):
    with io.BytesIO(data) as stream:
        codec = stream.read(1)[0]
        if codec != 1:
            raise NotImplementedError(codec)

        buffer = [0 for _ in range(4370)]
        src_left = read_uint32le(stream.read(4))

        buf_pos = 4096 - 18
        len_cmd = 100
        pos = 0

        buffer[:buf_pos] = [32 for _ in range(buf_pos)]

        im_buffer = [0 for _ in range(width * height)]

        cmd_var = 0
        while pos < width * height:
            assert src_left > 0

            cmd_var >>= 1
            if cmd_var & 0x100 == 0:
                cmd_var = stream.read(1)[0] | 0xFF00

            if cmd_var & 1 != 0:
                temp = stream.read(1)[0]
                im_buffer[pos] = temp
                pos += 1

                buffer[buf_pos] = temp
                buf_pos = (buf_pos + 1) % 4096
            else:
                offset = stream.read(1)[0]
                temp = stream.read(1)[0]

                offset |= (temp & 0xF0) << 4
                offset %= 4096
                str_len = (temp & 0x0F) + 3

                if str_len == len_cmd:
                    str_len = stream.read(1)[0] + 18
                
                for counter2 in range(str_len):
                    temp = buffer[(offset + counter2) % 4096]
                    im_buffer[pos] = temp
                    pos += 1

                    buffer[buf_pos] = temp
                    buf_pos = (buf_pos + 1) % 4096

                assert str_len < src_left, (str_len, src_left)

            src_left -= 1
        assert stream.read() == b''
        return im_buffer


def grouper(iterable, n, fillvalue=None):
    "Collect data into non-overlapping fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx
    args = [iter(iterable)] * n
    return itertools.zip_longest(*args, fillvalue=fillvalue)


def compress_sprite(data):
    out = bytearray()
    out += b'\x01\x02\x01'
    out += len(data).to_bytes(4, byteorder='little', signed=False)
    out += b''.join(b'\xff' + bytes(seq) for seq in grouper(data, 8))
    return bytes(out)



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
        v &= 0x0F
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
            print('DEC', val, len(out), repeat)
        assert len(out) == width * height, (len(out), width, height)
        res = list(out)
        if res:
            enc = pack_sprite(res)
            assert enc == data, (enc, data)
        return res


palette = [((53 + x) ** 2 * 13 // 5) % 256 for x in range(256 * 3)]

palette = [
	0x00, 0x00, 0x00,
	0x00, 0x00, 0x2A,
	0x00, 0x2A, 0x00,
	0x00, 0x2A, 0x2A,
	0x2A, 0x00, 0x00,
	0x2A, 0x00, 0x2A,
	0x2A, 0x15, 0x00,
	0x2A, 0x2A, 0x2A,
	0x15, 0x15, 0x15,
	0x15, 0x15, 0x3F,
	0x15, 0x3F, 0x15,
	0x15, 0x3F, 0x3F,
	0x3F, 0x15, 0x15,
	0x3F, 0x15, 0x3F,
	0x3F, 0x3F, 0x15,
	0x3F, 0x3F, 0x3F,
]
palette = palette * 16
assert len(palette) == 0x300
palette = [x << 2 for x in palette]


if __name__ == '__main__':

    if not len(sys.argv) > 3:
        print('Usage: insert_ext.py FILENAME INDEX IMAGE')
        exit(1)
    filenames = sys.argv[1]
    inject_idx = int(sys.argv[2])
    inject_pic = sys.argv[3]

    filenames = sorted(glob.iglob(sys.argv[1]))

    print(filenames)

    outfile = bytearray()
    outdata = bytearray()

    for fname in filenames:
        print(fname)
        basename = os.path.basename(fname)
        _, ext = os.path.splitext(basename)
        if ext == '.EXT':
            with open(fname, 'rb') as f:
                res_data = f.read()
        elif ext == '.TOT':
            with open(fname, 'rb') as f:
                _, res_data = read_tot(f)
                f.seek(0)
                data = f.read()
                outfile += data.replace(res_data, b'')
                assert outfile + res_data == data
            if not res_data:
                continue

        assert res_data
        with io.BytesIO(res_data) as f:
            items_count = read_sint16le(f.read(2))
            unknown = f.read(1)[0]
            assert items_count > 0, (items_count)

            outfile += res_data[:3]

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

            goffset = 0

            for idx, (offset, size, width, height, packed) in enumerate(items):
                assert f.tell() == offset + table_off, (f.tell(), offset + table_off)
                data = f.read(size)
                offset = len(outdata)
                if idx != inject_idx:
                    outdata += data
                elif data[:2] == b'\x01\x02':
                    im_data = np.asarray(Image.open(inject_pic)).ravel()
                    assert len(im_data) == width * height
                    packed = compress_sprite(im_data)
                    outdata += packed
                else:
                    im_data = np.asarray(Image.open(inject_pic)).ravel()
                    assert len(im_data) == width * height
                    packed = pack_sprite(im_data)
                    outdata += packed

                outfile += b''.join([
                    offset.to_bytes(4, byteorder='little', signed=False),
                    len(data).to_bytes(2, byteorder='little', signed=False),
                    width.to_bytes(2, byteorder='little', signed=False),
                    height.to_bytes(2, byteorder='little', signed=False),
                ])

    with open('TRY.TOT', 'wb') as offf:
        offf.write(outfile + outdata)
