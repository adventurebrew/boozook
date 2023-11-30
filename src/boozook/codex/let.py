import io
from pathlib import Path
from boozook.archive import GameBase

from pakal.archive import ArchivePath

import numpy as np


from boozook.grid import create_char_grid, read_image_grid, resize_frame


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


palette = [((53 + x) ** 2 * 13 // 5) % 256 for x in range(256 * 3)]


def decode_font(
    game: GameBase,
    entry: ArchivePath,
    target: str | Path,
):
    target = Path(target)
    print(f'TRYING {entry.name}')
    try:
        with entry.open('rb') as f:
            data = f.read()

        flags, height, start, end = data[:4]
        width = flags & 0x7F

        data = data[4:]

        row_aligned_bits = (width - 1) // 8 + 1

        size = row_aligned_bits * height
        bit_width = width

        chars = range(start, end + 1)

        widths = {}
        print(flags)
        if flags & 0x80:
            widths = dict(
                zip(chars, data[size * len(chars) : size * (len(chars) + 1)]),
            )
        print(widths)

        char_data = [data[i * size : (i + 1) * size] for i in range(len(chars))]

        print(start, end)
        print(width, height)

        nwidth = 8 * ((width + 7) // 8)
        print((height, nwidth))

        glyphs = [
            np.unpackbits(
                np.frombuffer(data, dtype=np.uint8),
            ).reshape(
                height, nwidth
            )[:, :width]
            for data in char_data
        ]

        im = create_char_grid(chars.stop, zip(chars, glyphs))
        im.putpalette(palette)
        im.save(str(target / f'{entry.name}.png'))
    except Exception as exc:
        print(f'FAILED CONVERTING FILE: {entry.name}, {type(exc)}: {exc}')


def compose(
    game: GameBase,
    entry: ArchivePath,
    target: str | Path,
):
    frames = read_image_grid(str(target / f'{entry.name}.png'))
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

    with io.BytesIO() as output:
        output.write(bytes([width, height, first_char, last_char]))
        for c in char_range:
            output.write(encoded_chars.get(c, spacer))
            print('DATA', c, encoded_chars.get(c, spacer))

        game.patch(entry.name, output.getvalue())
