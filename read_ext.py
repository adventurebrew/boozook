import io
import os
import sys
import glob

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

        buf_pos = 4078
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


def unpack_sprite(data, width, height):
    im_buffer = [0 for _ in range(width * height)]

    pos = 0
    with io.BytesIO(data) as stream:
        while pos < width * height:
            val = stream.read(1)[0]
            repeat = val & 7
            val &= 0xF8

            if not val & 8:
                repeat <<= 8
                repeat %= 4096 * 4096
                repeat |= stream.read(1)[0]
            repeat += 1
            val >>= 4

            im_buffer[pos:pos+repeat] = [val for _ in range(repeat)]
            pos += repeat
        return im_buffer


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

    if not len(sys.argv) > 1:
        print('Usage: extract_cat.py FILENAME')
        exit(1)
    filenames = sys.argv[1]

    filenames = sorted(glob.iglob(sys.argv[1]))

    print(filenames)

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
            if not res_data:
                continue

        assert res_data
        with io.BytesIO(res_data) as f:
            items_count = read_sint16le(f.read(2))
            unknown = f.read(1)[0]
            assert items_count > 0, (items_count)

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
                    print('UNCOMPRESS', basename, idx)
                    im = uncompress_sprite(data[2:], width, height)
                else:
                    print('UNPACK', basename, idx)
                    im = unpack_sprite(data, width, height)
                if width & height:
                    bim = convert_to_pil_image(im, size=(width, height))
                    bim.putpalette([(x << 2) % 256 for x in palette])
                    bim.save(f'out-gob2/{basename}_{idx}.png')
                    print(f'out-gob2/{basename}_{idx}.png')
                elif len(data) == 768:
                    print('PALETTE', basename, idx)
                    palette = list(data)
                    bim.putpalette([(x << 2) % 256 for x in palette])
                    bim.save(f'out-gob2/{basename}_{idx}.png')
                else:
                    print(len(data), len(im))
