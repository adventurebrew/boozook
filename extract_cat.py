import os
from posixpath import basename
import sys
import glob

LENS = {
    'MENU.CAT': 40,
    'MONDE1.CAT': 14,
    'MONDE2.CAT': 26,
    'MONDE3.CAT': 15,
    'MONDE4.CAT': 12,
    'MONDE5.CAT': 15,
    'MONDE6.CAT': 17,
    'MONDE7.CAT': 10,
    'GOB00.CAT': 20,
    'GOB01.CAT': 20,
    'GOB02.CAT': 20,
    'GOB03.CAT': 20,
    'GOB04.CAT': 20,
    'GOB05.CAT': 20,
    'GOB06.CAT': 20,
    'GOB07.CAT': 20,
    'GOB08.CAT': 20,
    'GOB09.CAT': 20,
    'GOB10.CAT': 20,
    'GOB11.CAT': 20,
    'GOB12.CAT': 20,
    'GOB13.CAT': 20,
    'GOB14.CAT': 20,
    'GOB15.CAT': 20,
    'GOB16.CAT': 20,
    'GOB17.CAT': 20,
    'GOB18.CAT': 20,
    'GOB19.CAT': 20,
    'GOB20.CAT': 20,
    'GOB21.CAT': 20,
    'GOB22.CAT': 20,
}


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
                for _ in range(LENS[basename.upper()]):
                    line = f.read(40)
                    if not line:
                        stopped = True
                        break
                    line, rest = line.split(b'\0', maxsplit=1)
                    assert set(rest) == {0} or set(rest) == {0, ord(' ')}, rest
                    if idx == 2:
                        print(basename, idx, line.decode(errors='ignore'), sep='\t')
                idx += 1
