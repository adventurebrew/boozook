import io
import os
import numpy as np

from grid import create_char_grid

palette = [((53 + x) ** 2 * 13 // 5) % 256 for x in range(256 * 3)]

if __name__ == '__main__':
    import sys
    import glob

    if not len(sys.argv) > 1:
        print('Usage: gob_font.py FILENAME')
        exit(1)
    filenames = sys.argv[1]

    filenames = list(glob.iglob(sys.argv[1]))
    print(filenames)

    for fname in filenames:
        basename = os.path.basename(fname)
        print(f'TRYING {basename}')
        try:

            with open(fname, 'rb') as f:
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
                widths = dict(zip(chars, data[size * len(chars): size * (len(chars) + 1)]))
            print(widths)

            char_data = [data[i*size:(i + 1)*size] for i in range(len(chars))]


            print(start, end)
            print(width, height)

            nwidth = 8 * ((width + 7) // 8)
            print((height, nwidth))

            glyphs = [np.unpackbits(np.frombuffer(data, dtype=np.uint8)).reshape(height, nwidth)[:, :width] for data in char_data]

            im = create_char_grid(chars.stop, zip(chars, glyphs))
            im.putpalette(palette)
            im.save(os.path.join('out', f'{basename}.png'))
        except Exception as exc:
            print(f'FAILED CONVERTING FILE: {basename}, {type(exc)}: {exc}')
