from datetime import datetime
import io
from pathlib import Path
from boozook.codex.base import write_uint32_le

from boozook.codex.stk import STK21FileEntry, STKFileEntry, unpack_chunk


def check_dico(unpacked, unpacked_index, counter, dico, dico_index):
    best_pos = 0
    best_length = 2

    if counter < 3:
        return None

    template = dico[:4096] + dico[:18]

    for i in range(min(18, counter), 2, -1):
        pattern = unpacked[unpacked_index : unpacked_index + i]
        pos = template.find(pattern)
        while pos != -1:
            if not (pos < dico_index <= pos + i - 1):
                assert 0 <= pos < 4096
                best_pos = pos
                best_length = i
                return (True, best_pos, best_length)
            pos = template.find(pattern, pos + 1)

    return (False, best_pos, 0)


def pack_content(data):
    with io.BytesIO() as output:
        dico_index = 4078
        dico = bytearray(b'\x20' * dico_index + b'\x20' * 36)
        write_buffer = bytearray(17)

        size = len(data)
        unpacked = data + b'\0'

        output.write(size.to_bytes(4, byteorder='little', signed=False))

        dico[dico_index : dico_index + 3] = unpacked[:3]
        dico_index += 3

        write_buffer[1] = unpacked[0]
        write_buffer[2] = unpacked[1]
        write_buffer[3] = unpacked[2]

        cmd = (1 << 3) - 1
        counter = size - 3
        unpacked_index = 3
        cpt = 3
        buff_index = 4

        size = 4
        resultcheckpos = 0
        resultchecklength = 0

        while counter > 0:
            cdico = False
            checked = check_dico(unpacked, unpacked_index, counter, dico, dico_index)
            if checked is not None:
                cdico, resultcheckpos, resultchecklength = checked
            if not cdico:
                dico[dico_index] = unpacked[unpacked_index]
                write_buffer[buff_index] = unpacked[unpacked_index]
                cmd |= 1 << cpt
                unpacked_index += 1
                dico_index = (dico_index + 1) % 4096
                buff_index += 1
                counter -= 1
            else:
                for i in range(resultchecklength):
                    dico[((dico_index + i) % 4096)] = dico[
                        ((resultcheckpos + i) % 4096)
                    ]

                write_buffer[buff_index] = resultcheckpos & 0xFF
                write_buffer[buff_index + 1] = ((resultcheckpos & 0x0F00) >> 4) + (
                    resultchecklength - 3
                )

                unpacked_index += resultchecklength
                dico_index = (dico_index + resultchecklength) % 4096
                resultcheckpos = (resultcheckpos + resultchecklength) % 4096

                buff_index += 2
                counter -= resultchecklength

            if cpt == 7 or counter == 0:
                write_buffer[0] = cmd
                output.write(write_buffer[:buff_index])
                size += buff_index
                buff_index = 1
                cmd = 0
                cpt = 0
            else:
                cpt += 1

        with io.BytesIO(output.getbuffer()) as packed:
            size = int.from_bytes(packed.read(4), byteorder='little', signed=False)
            reunpacked = unpack_chunk(
                packed,
                size,
            )
            if data != reunpacked:
                print(data[:100])
                print(reunpacked[:100])
                print(reunpacked[:100] == data[:100])
            assert data == reunpacked
        return output.getvalue()


def write_header(index):
    with io.BytesIO() as output:
        count = len(index)
        base_offset = 22 * count + 2

        output.write(count.to_bytes(2, byteorder='little', signed=False))

        for fname, content in index.items():
            output.write(
                fname.ljust(13, '\0').encode('ascii')
                + write_uint32_le(content.size)
                + write_uint32_le(content.offset + base_offset)
                + bytes([int(content.compression)])
            )
        return output.getvalue()


def recompress_archive(archive, patches, target, force_recompress=False):
    target = Path(target)
    index = {}
    orig_offs = {}
    with io.BytesIO() as output:
        for file in archive:
            compression = archive.index[file.name].compression
            print(
                file.name,
                int(compression),
                archive.index[file.name],
            )
            orig_data = file.read_bytes()
            patch_data = patches.pop(file.name, orig_data)
            uncompressed_size = len(patch_data)
            if orig_data != patch_data or force_recompress:
                content = pack_content(patch_data) if compression else patch_data
            else:
                # Skip files that should stay the same as packing the content takes long time
                with archive._read_entry(
                    archive.index[file.name]._replace(compression=False) if archive.version != 2.1 else archive.index[file.name]._replace(compression=False, uncompressed_size=None)
                ) as stream:
                    content = stream.read()
            dup = orig_offs.get(archive.index[file.name], None)
            if dup:
                index[file.name] = dup
                continue
            fname = file.name if compression != 2 else file.with_suffix('.0OT').name
            index[fname] = (
                STKFileEntry(output.tell(), len(content), compression)
                if archive.version != 2.1
                else archive.index[file.name]._replace(
                    offset=output.tell(),
                    size=len(content),
                    compression=compression,
                    uncompressed_size=uncompressed_size
                )
            )
            if len(content) % 2 and archive.version != 2.1:
                content += b'\0'
            output.write(content)
            orig_offs[archive.index[file.name]] = index[fname]
        for fname, content in patches.items():
            assert fname not in index, (list(index.keys()), list(patches.keys()))
            index[fname] = (
                STKFileEntry(output.tell(), len(content), False)
                if archive.version != 2.1
                else archive.index[file.name]._replace(
                    offset=output.tell(),
                    size=len(content),
                    compression=False,
                    uncompressed_size=uncompressed_size,
                    # TODO: Allow setting modified date and creator
                    modified=datetime.now(),
                    creator='Boozook',
                )
            )
            if len(content) % 2 and archive.version != 2.1:
                content += b'\0'
            output.write(content)

        # TODO: Allow preserve / modify
        ctime = datetime.now().strftime('%d%m%Y%H%M%S').encode('ascii')
        creator = 'Boozook'.ljust(8, '\0').encode('ascii')[:8]

        if archive.version == 2.1:
            filename_offset = output.tell() + 32
            header = b'STK2.1' + ctime + creator + write_uint32_le(filename_offset)
            filename_offset += 8
            first_name_offset = filename_offset
            misc = bytearray()
            names = bytearray()
            for fname, entry in index.items():
                misc += write_uint32_le(filename_offset)
                names += fname.encode('ascii') + b'\0'
                filename_offset += len(fname) + 1
                misc += (
                    entry.modified.strftime('%d%m%Y%H%M%S').encode('ascii')
                    + entry.created.strftime('%d%m%Y%H%M%S').encode('ascii')
                    + entry.creator.ljust(8, '\0').encode('ascii')[:8]
                )
                misc += write_uint32_le(entry.size)
                misc += write_uint32_le(entry.uncompressed_size)
                misc += entry.unk
                misc += write_uint32_le(entry.offset + 32)
                misc += write_uint32_le(entry.compression)
            target.write_bytes(header + output.getvalue() + write_uint32_le(len(index)) + write_uint32_le(first_name_offset + len(names)) + names + misc)
            return
        header = write_header(index)
        target.write_bytes(header + output.getvalue())
