import sys
import os
import io

def read_uin16le(f):
    return int.from_bytes(f.read(2), byteorder='little', signed=False)

def read_uin32le(f):
    return int.from_bytes(f.read(4), byteorder='little', signed=False)

def replace_many(s, *reps):
    for r in reps:
        s = s.replace(*r)
    return s

def extract(f):
    file_count = read_uin16le(f)
    for i in range(file_count):
        file_name = f.read(13).decode().split('\0')[0]
        size = read_uin32le(f)
        offset = read_uin32le(f)
        compression = f.read(1) != b'\00'

        # Replacing cyrillic characters
        reps = ('\x85', 'E'), ('\x8A', 'K'), ('\x8E', 'O'), ('\x91', 'C'), ('\x92', 'T')
        file_name = replace_many(file_name, *reps)

        yield file_name, size, offset, compression

def unpack_chunk(stream, size):
    tmp_buf = [0x20 for _ in range(4078)] + [0 for _ in range(36)]
    tmp_ind = 4078
    cmd = 0
    res = b''
    while True:
        cmd >>= 1
        if cmd & 0x0100 == 0:
            cmd = ord(stream.read(1)) | 0xFF00
        if cmd & 1 != 0:
            tmp = stream.read(1)
            res += tmp
            tmp_buf[tmp_ind] = tmp
            tmp_ind += 1
            tmp_ind %= 4096
            size -= 1
            if not size:
                break
        else:
            tmp1 = ord(stream.read(1))
            tmp2 = ord(stream.read(1))

            off = tmp1 | ((tmp2 & 0xF0) << 4)
            ln = ((tmp2 & 0x0F) + 3) % 256

            for i in range(ln):
                res += bytes(tmp_buf[(off + i) % 4096])
                size -= 1
                if not size:
                    return res

                tmp_buf[tmp_ind] = tmp_buf[(off + i) % 4096]
                tmp_ind += 1
                tmp_ind %= 4096
    return res

def unpack(data, compression):
    if not compression:
        return data
    stream = io.BytesIO(data)
    size = read_uin32le(stream)
    return unpack_chunk(stream, size)

if __name__ == '__main__':
    if not len(sys.argv) > 1:
        print('Usage: extract.py FILENAME')
        exit(1)
    fname = sys.argv[1]

    # extract files
    with open(fname, 'rb') as stk_file:
        index = list(extract(stk_file))
        for file_name, size, offset, compression in index:
            if (stk_file.tell() & 1):
                pad = stk_file.read(1)
                assert pad == b'\00', pad
            assert stk_file.tell() == offset
            stk_file.seek(offset, 0)
            print([x for x in file_name])
            basedir = os.path.join('out', os.path.basename(fname))
            os.makedirs(basedir, exist_ok=True)
            with open(os.path.join(basedir, file_name), 'wb') as out:
                data = stk_file.read(size)
                # assert not compression, compression
                out.write(unpack(data, compression))
