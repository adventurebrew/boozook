import io
import os
import sys
import glob

from PIL import Image
import numpy as np
from boozook.codex.ext import (
    pack_sprite,
    read_sint16le,
    read_uint16le,
    read_uint32le,
    uncompress_sprite,
)
from boozook.codex.stk_compress import pack_content

from boozook.totfile import read_tot


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
                _, _, _, res_data = read_tot(f)
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
            assert items_count > 0, items_count

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

                outfile += b''.join(
                    [
                        offset.to_bytes(4, byteorder='little', signed=False),
                        len(data).to_bytes(2, byteorder='little', signed=False),
                        width.to_bytes(2, byteorder='little', signed=False),
                        height.to_bytes(2, byteorder='little', signed=False),
                    ]
                )

    with open('TRY.TOT', 'wb') as offf:
        offf.write(outfile + outdata)
