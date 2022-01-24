import os
import sys
import glob
import itertools


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

LANG_CODE = 8  # HEBREW
LINE_SIZE = 40

if __name__ == '__main__':

    if not len(sys.argv) > 1:
        print('Usage: extract_cat.py FILENAME CATALOG')
        exit(1)
    filenames = sys.argv[1]
    fcatalog = sys.argv[2]

    filenames = sorted(glob.iglob(sys.argv[1]))

    with open(fcatalog, 'r', encoding='utf-8') as cf:
        catalog = cf.readlines()

    catalog = [line[:-1].split('\t', maxsplit=3) for line in catalog]

    for fname in filenames:
        basename = os.path.basename(fname)
        lcatalog = [line for file, lang_num, line in catalog if file == basename]
        print(lcatalog)
        with open(fname, 'rb') as f, open(os.path.join('out-gob2', basename), 'wb') as out:
            version = f.read(18)
            out.write(version)
            idx = 0
            stopped = False
            while not stopped:
                for _ in range(LENS[basename.upper()]):
                    line = f.read(LINE_SIZE)
                    out.write(line)
                    if not line:
                        stopped = True
                        break
                    line, rest = line.split(b'\0', maxsplit=1)
                    # assert set(rest) == {0}, rest
                    if idx == 2:
                        print(basename, idx, line.decode())
                idx += 1
        
            out.seek(len(version) + LANG_CODE * LENS[basename.upper()] * LINE_SIZE, 0)
            for line in lcatalog:
                enc = line.encode('windows-1255')[::-1]
                towrite = enc + b'\0' * (LINE_SIZE - len(enc))
                assert len(towrite) == LINE_SIZE, len(towrite)
                out.write(towrite)
