import os
from posixpath import basename
import sys
import glob


if __name__ == '__main__':

    if not len(sys.argv) > 1:
        print('Usage: extract_cat.py FILENAME')
        exit(1)
    filenames = sys.argv[1]

    filenames = sorted(glob.iglob(sys.argv[1]))

    print(filenames)

    for fname in filenames:
        basename = os.path.basename(fname)
        with open(fname, 'rb') as f:
            version = f.read(18)
            idx = 0
            stopped = False
            while not stopped:
                # for _ in range(20):
                line = f.read(40)
                if not line:
                    stopped = True
                    break
                line, rest = line.split(b'\0', maxsplit=1)
                if set(rest) != {0}:
                    print('WARNING:', rest)
                print(basename, idx, line.decode(errors='ignore'), sep='\t')
                # idx += 1
