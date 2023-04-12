import os
import io
import sys

import itertools

import numpy as np
from grid import read_image_grid, resize_frame

def read_sint16le(stream):
    return int.from_bytes(stream.read(2), byteorder='little', signed=True)

def write_sint16le(number):
    return number.to_bytes(2, byteorder='little', signed=True)

def write_uint16le(number):
    return number.to_bytes(2, byteorder='little', signed=False)

def padarray(A, size):
    t = size - len(A)
    return np.pad(A, pad_width=(0, t), mode='constant')

def encode_char(data, flags=0):
    # TODO: align data width to multiple of 8
    # data = np.hstack([data, np.zeros((16, 4), dtype=np.uint8)])
    print(data.shape)
    data = 1 * (data == 1)
    return bytes(np.packbits(data).ravel().tolist())

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('no filename given')
        exit(1)

    filename = sys.argv[1]
    target = 'new-font.let'
    frames = read_image_grid(filename)
    frames = enumerate(resize_frame(frame) for frame in frames)
    available = [(idx, char) for idx, char in frames if char is not None]

    print(available)

    first_char, _ = available[0]
    last_char, _ = available[-1]
    height, width = available[0][1][1].shape
    print(height, width)
    print(first_char, last_char)
    char_range = range(first_char, last_char + 1)
    assert len(char_range) == (last_char - first_char + 1)
    encoded_chars = {idx: encode_char(char) for idx, (loc, char) in available}

    nwidth = 8 * ((width + 7) // 8)
    print((height, nwidth))    

    spacer = encode_char(np.zeros((height, nwidth)))

    with open(target, 'wb') as output:
        output.write(bytes([width, height, first_char, last_char]))
        for c in char_range:
            output.write(encoded_chars.get(c, spacer))
            print('DATA', c, encoded_chars.get(c, spacer))
