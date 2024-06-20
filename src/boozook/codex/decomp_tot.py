from collections import defaultdict
from contextlib import redirect_stdout
from functools import partial
import io
import os
from pathlib import Path
from boozook import archive
from boozook.codex import tot
from boozook.codex.crypt import CodePageEncoder, HebrewKeyReplacer
from boozook.codex.ext import read_ext_table
from boozook.codex.let import read_sint16le
from boozook.codex.stk import replace_many, unpack_chunk
from boozook.text import decrypt

from boozook.totfile import (
    read_tot,
    read_uint16le,
    read_uint32le,
    reads_uint16le,
    reads_uint32le,
)


def peek_uint8(scf):
    res = ord(scf.read(1))
    scf.seek(-1, 1)
    return res


OPERATORS = {
    9: '(',
    11: '!',
    10: ')',
    1: '-',
    2: '+',
    3: '-',
    4: '|',
    5: '*',
    6: '/',
    7: '%',
    8: '&',
    30: '||',
    31: '&&',
    32: '<',
    33: '<=',
    34: '>',
    35: '>=',
    36: '==',
    37: '!=',
}


def read_str(stream):
    return b''.join(iter(partial(stream.read, 1), b'\00')).decode(
        'ascii', errors='ignore'
    )


def paren(func):
    def inner(*args, **kwargs):
        res = func(*args, **kwargs)
        if ' ' in res:
            return f'({res})'
        return res

    return inner


@paren
def read_expr(scf, stop=99):
    num = 0
    expr = ''
    # print('BEGIN READ_EXPR')
    while True:
        operation = scf.read(1)[0]

        # print('OPERATION', operation)

        # var_base = 0
        while operation in {14, 15}:
            if operation == 14:
                expr += '#{:d}#'.format(read_uint16le(scf.read(2)) * 4)

                _skip = scf.read(2)
                if peek_uint8(scf) == 97:
                    _skip = scf.read(1)

            elif operation == 15:
                expr += '#{:d}->'.format(read_uint16le(scf.read(2)) * 4)

                offset1 = read_uint16le(scf.read(2))

                dim_count = scf.read(1)[0]
                dim_array = scf.read(dim_count)

                for i in range(dim_count):
                    expr += read_expr(scf, 12) + '->'

                expr += '#'

                if peek_uint8(scf) == 97:
                    _skip = scf.read(1)

            operation = scf.read(1)[0]

        if 16 <= operation <= 29:
            if operation == 17:
                expr += 'var16_{:d}'.format(read_uint16le(scf.read(2)) * 2)
            elif operation == 18:
                expr += 'var8_{:d}'.format(read_uint16le(scf.read(2)))
            elif operation == 19:
                expr += '{:d}'.format(read_uint32le(scf.read(4)))

            elif operation == 20:
                expr += '{:d}'.format(read_uint16le(scf.read(2)))

            elif operation == 21:
                expr += '{:d}'.format(scf.read(1)[0])
            elif operation == 22:
                expr += '"{}"'.format(read_str(scf))

            elif operation in {23, 24}:
                expr += 'var32_{:d}'.format(read_uint16le(scf.read(2)) * 4)
            elif operation == 25:
                expr += '(&var8_{:d})'.format(read_uint16le(scf.read(2)) * 4)
                if peek_uint8(scf) == 13:
                    _skip = scf.read(1)
                    expr += '+{*'
                    expr += read_expr(scf, 12)

            elif operation in {16, 26, 27, 28}:
                temp = read_uint16le(scf.read(2))
                if operation == 16:
                    expr += 'var8_{:d}['.format(temp)
                elif operation == 26:
                    expr += 'var32_{:d}['.format(temp * 4)
                elif operation == 27:
                    expr += 'var16_{:d}['.format(temp * 2)
                elif operation == 28:
                    expr += '(&var8_{:d}['.format(temp * 4)
                dim_count = scf.read(1)[0]
                arr_desc = scf.read(dim_count)
                offset = 0
                for dim in range(dim_count):
                    expr += read_expr(scf, 12) + ' of {:d}'.format(
                        read_uint16le(arr_desc[2 * dim : 2 * (dim + 1)])
                    )
                    if dim < dim_count - 1:
                        expr += ']['
                expr += ']'

                if operation == 28:
                    expr += ')'
                if operation == 28 and peek_uint8(scf) == 13:
                    _skip = scf.read(1)
                    expr += '+{*' + read_expr(scf, 12)

            elif operation == 29:
                func = reads_uint8(scf)
                FUNCS = {
                    5: 'sqr',
                    10: 'rand',
                    7: 'abs',
                    0: 'sqrt',
                    1: 'sqrt',
                    6: 'sqrt',
                }
                expr += FUNCS.get(func, 'id') + '( ' + read_expr(scf, 10)
        elif operation in OPERATORS:
            expr += ' ' + OPERATORS[operation] + ' '

        elif operation == 12:
            expr += '}'
            if stop != 12:
                print('WARNING: closing paren without opening?')

        elif operation == 99:
            pass

        else:
            while ord(scf.read(1)) != stop:
                pass
            return expr + f'<unknown operator {operation}'
            # raise ValueError(f'Unknown operator {operation}')

        if operation == 9:
            num += 1
            continue

        if operation == 10:
            num -= 1
        elif operation in OPERATORS:
            continue

        if operation == stop:
            if stop != 10 or num < 0:
                return replace_many(expr, *named_variables.items())
                # return expr


@paren
def read_var_index(scf, arg_0=0, arg_4=0):
    num = 0
    expr = ''
    pref = ''

    operation = ord(scf.read(1))

    # var_base = 0
    while operation in {14, 15}:
        if operation == 14:
            pref += '#{:d}#'.format(read_uint16le(scf.read(2)) * 4)

            _skip = scf.read(2)
            if peek_uint8(scf) == 97:
                _skip = scf.read(1)
            else:
                return expr

        elif operation == 15:
            pref += '#{:d}->'.format(read_uint16le(scf.read(2)) * 4)

            offset1 = read_uint16le(scf.read(2))

            dim_count = scf.read(1)[0]
            dim_array = scf.read(dim_count)

            for i in range(dim_count):
                pref += read_expr(scf, 12) + '->'

            pref += '#'

            if peek_uint8(scf) == 97:
                _skip = scf.read(1)
            else:
                return expr

        operation = scf.read(1)[0]

    if operation in {16, 18, 25, 28}:
        expr = 'var8_'
    elif operation in {17, 24, 27}:
        expr = 'var16_'
    elif operation in {23, 26}:
        expr = 'var32_'

    expr += pref

    if operation in {23, 24, 25}:
        expr += '{}'.format(read_uint16le(scf.read(2)) * 4)
        if operation == 25 and peek_uint8(scf) == 13:
            _skip = scf.read(1)
            expr += '+{*'
            expr += read_expr(scf, 12)

    elif operation == 17:
        expr += '{}'.format(read_uint16le(scf.read(2)) * 2)
    elif operation == 18:
        expr += '{}'.format(read_uint16le(scf.read(2)))

    elif operation in {16, 26, 27, 28}:
        if operation == 16:
            expr += '{}['.format(read_uint16le(scf.read(2)))
        elif operation == 26:
            expr += '{}['.format(read_uint16le(scf.read(2)) * 4)
        elif operation == 27:
            expr += '{}['.format(read_uint16le(scf.read(2)) * 2)
        elif operation == 28:
            expr += '{}['.format(read_uint16le(scf.read(2)) * 4)

        dim_count = scf.read(1)[0]
        arr_desc = scf.read(dim_count)
        for dim in range(dim_count):
            expr += read_expr(scf, 12) + ' of {:d}'.format(
                read_uint16le(arr_desc[2 * dim : 2 * (dim + 1)])
            )
            if dim < dim_count - 1:
                expr += ']['
        expr += ']'

        if operation == 28 and peek_uint8(scf) == 13:
            _skip = scf.read(1)
            expr += '+{*'
            expr += read_expr(scf, 12)

    else:
        expr += 'var_0'

    return replace_many(expr, *named_variables.items())
    # return expr


def xparam(name):
    def inner(scf):
        raise NotImplementedError(name)

    return inner


def gparam(name):
    def inner(scf):
        globals()[name](scf)

    return inner


def fparam(name, *params):
    def inner(scf):
        printl(f'{name}', *(param(scf) for param in params))

    return inner


def o1_callSub(scf):
    offset = read_uint16le(scf.read(2))
    printl('o1_callSub', offset)
    ctx['functions'].append(offset)


def o2_assign(scf):
    dest_type = peek_uint8(scf)
    var_index = read_var_index(scf)

    if peek_uint8(scf) == 99:
        _skip = scf.read(1)
        loop_count = scf.read(1)[0]

        DIVERGE_FROM_DEGOB = True
        if DIVERGE_FROM_DEGOB:
            expr = ', '.join(read_expr(scf) for _ in range(loop_count))
            printl("{} = [{}]".format(var_index, expr))
        else:
            for i in range(loop_count):
                expr = read_expr(scf)
                printl(
                    "{}[{}] = {}".format(
                        var_index, i * 2 if dest_type == 24 else i, expr
                    )
                )
    else:
        expr = read_expr(scf)
        printl("{} = {}".format(var_index, expr))


def reads_uint8(stream):
    return ord(stream.read(1))


def video_o2_loadMult(scf):
    iid = reads_uint16le(scf)
    if iid & 0x8000:
        iid &= 0x7FFF
        _skip = scf.read(1)

    data = read_ext_item(
        ctx['ext_items'], iid - 30000, ctx['ext_data'], ctx['com_entry'] and ctx['com_data'][ctx['com_entry'].name]
    )

    with io.BytesIO(data) as stream:
        static_count = reads_uint8(stream) + 1
        has_imds = static_count & 0x80 != 0
        static_count &= 0x7F
        static_count %= 256
        anim_count = reads_uint8(stream) + 1
        anim_count %= 256

        for i in range(static_count):
            read_expr(scf)
            s_size = reads_uint16le(scf)
            _skip = scf.read(s_size * 2)
            s_size = reads_uint16le(scf)
            _skip = scf.read(2 + s_size * 8)

            stream.read(14)

        for i in range(anim_count):
            read_expr(scf)
            s_size = reads_uint16le(scf)
            _skip = scf.read(2 + s_size * 8)

            stream.read(14)

        stream.read(2)

        count1 = read_sint16le(stream)
        stream.read(count1 * 4)

        for i in range(4):
            count1 = read_sint16le(stream)
            stream.read(count1 * 10)

        stream.read(5 * 16 * 3)

        count1 = read_sint16le(stream)
        stream.read(count1 * 7)

        count1 = read_sint16le(stream)
        stream.read(count1 * 80)

        count1 = read_sint16le(stream)
        stream.read(count1 * (4 + (0 if has_imds else 24)))

        count1 = read_sint16le(stream)
        for i in range(count1):
            stream.seek(2, 1)
            cmd = read_sint16le(stream)

            stream.seek(-4, 1)

            if cmd in {1, 4}:
                _skip = scf.read(2)
            elif cmd == 3:
                _skip = scf.read(4)
            stream.read(12 + (0 if has_imds else 24))

        if has_imds:
            s_size = reads_uint16le(scf)
            _skip = scf.read(s_size * 2)

            if tot_file[41] >= 51:
                s_size = reads_uint16le(scf)
                _skip = scf.read(s_size * 14)

    return (iid,)


def video_o1_loadAnim(scf):
    tmp = (read_expr(scf), reads_uint16le(scf), reads_uint16le(scf))
    return tmp + (scf.read(tmp[1] * 8),)


def video_o2_loadMapObjects(scf):
    some, iid = read_var_index(scf), reads_uint16le(scf)
    more = []
    if iid < 65520:
        count = reads_uint16le(scf)
        more = [reads_uint16le(scf) for _ in range(count)]
    return some, iid, tuple(more)


def video_o2_loadMultObject(scf):
    f, s, t = read_expr(scf), read_expr(scf), read_expr(scf)

    options = (
        'animation',
        'layer',
        'frame',
        'animType',
        'order',
        'isPaused',
        'isStatic',
        'maxTick',
        'maxFrame',
        'newLayer',
        'newAnimation',
    )
    r = dict(zip(options, (read_expr(scf) for _ in options)))
    return f, s, t, r


def video_o2_totSub(scf):
    length = reads_uint8(scf)
    args = read_expr(scf) if length & 0x80 else scf.read(length)
    return args, reads_uint8(scf)


def video_o1_loadStatic(scf):
    expr = read_expr(scf)
    s_size1 = reads_uint16le(scf)
    _skip = scf.read(s_size1 * 2)
    s_size2 = reads_uint16le(scf)
    num = reads_uint16le(scf)
    _skip = scf.read(s_size2 * 8)

    return expr, s_size1, s_size2, num


def video_o2_pushVars(scf):
    count = reads_uint8(scf)
    params = []

    for i in range(count):
        if peek_uint8(scf) in {25, 28}:
            params.append((read_var_index(scf), 'animDataSize'))
            _skip = scf.read(1)
        else:
            params.append((read_var_index(scf), 4))

    return params


def video_o2_playMult(scf):
    mult_data = reads_uint16le(scf)
    return mult_data >> 1, mult_data & 1


def vparam(name, *params):
    def inner(scf):
        printl(f'(D) {name}', *(param(scf) for param in params))

    return inner


def lvparam(name, lfunc):
    def inner(scf):
        printl(f'(D) {name}', *lfunc(scf))

    return inner


def cparam(name, *params):
    def inner(scf):
        printl(f'(G) {name}', *(param(scf) for param in params))

    return inner


def lcparam(name, lfunc):
    def inner(scf):
        printl(f'(G) {name}', *lfunc(scf))

    return inner


video_ops = {
    0x00: lvparam('o2_loadMult', video_o2_loadMult),
    0x01: lvparam('o2_playMult', video_o2_playMult),
    0x02: vparam('o2_freeMultKeys', reads_uint16le),
    0x07: vparam(
        'o1_initCursor',
        read_var_index,
        read_var_index,
        reads_uint16le,
        reads_uint16le,
        reads_uint16le,
    ),
    0x08: vparam(
        'o1_initCursorAnim', read_expr, reads_uint16le, reads_uint16le, reads_uint16le
    ),
    0x09: vparam('o1_clearCursorAnim', read_expr),
    0x0A: vparam('o2_setRenderFlags', read_expr),
    0x10: lvparam('o1_loadAnim', video_o1_loadAnim),
    0x11: vparam('o1_freeAnim', read_expr),
    0x13: vparam('o2_multSub', read_expr, read_expr, read_expr, read_expr, read_expr),
    0x14: vparam(
        'o2_initMult',
        reads_uint16le,
        reads_uint16le,
        reads_uint16le,
        reads_uint16le,
        reads_uint16le,
        read_var_index,
        read_var_index,
        read_var_index,
    ),
    0x15: vparam('o1_freeMult'),
    0x16: vparam('o1_animate'),
    0x17: lvparam('o2_loadMultObject', video_o2_loadMultObject),
    0x19: vparam(
        'o1_getObjAnimSize',
        read_expr,
        read_var_index,
        read_var_index,
        read_var_index,
        read_var_index,
    ),
    0x1A: lvparam('o1_loadStatic', video_o1_loadStatic),
    0x1B: vparam('o1_freeStatic', read_expr),
    0x1C: vparam('o2_renderStatic', read_expr, read_expr),
    0x1D: vparam('o2_loadCurLayer', read_expr, read_expr),
    0x20: vparam('o2_playCDTrack', read_expr),
    0x22: vparam('o2_stopCD'),
    0x23: vparam('o2_readLIC', read_expr),
    0x24: vparam('o2_freeLIC'),
    0x25: vparam('o2_getCDTrackPos', read_var_index, read_var_index),
    0x40: vparam('o2_totSub', video_o2_totSub),
    0x41: vparam('o2_switchTotSub', reads_uint16le, reads_uint16le),
    0x42: lvparam('o2_pushVars', video_o2_pushVars),
    0x50: lvparam('o2_loadMapObjects', video_o2_loadMapObjects),
    0x51: vparam('o2_freeGoblins'),
    0x52: vparam('o2_moveGoblin', read_expr, read_expr, read_expr),
    0x53: vparam('o2_writeGoblinPos', read_var_index, read_var_index, read_expr),
    0x54: vparam('o2_stopGoblin', read_expr),
    0x55: vparam('o2_setGoblinState', read_expr, read_expr, read_expr),
    0x56: vparam('o2_placeGoblin', read_expr, read_expr, read_expr, read_expr),
    0x80: vparam('o2_initScreen', reads_uint8, reads_uint8, read_expr, read_expr),
    0x81: vparam(
        'o2_scroll', read_expr, read_expr, read_expr, read_expr, read_expr, read_expr
    ),
    0x82: vparam('o2_setScrollOffset', read_expr, read_expr),
    0x83: vparam(
        'o2_playImd',
        read_expr,
        read_expr,
        read_expr,
        read_expr,
        read_expr,
        read_expr,
        read_expr,
        read_expr,
        read_expr,
    ),
    0x84: vparam(
        'o2_getImdInfo',
        read_expr,
        read_var_index,
        read_var_index,
        read_var_index,
        read_var_index,
        read_var_index,
    ),
    0x85: vparam('o2_openItk', read_expr),
    0x86: vparam('o2_closeItk'),
}


def o1_drawOperations(scf):
    vop = ord(scf.read(1))
    vfunc = video_ops.get(vop)
    if vfunc is None:
        raise ValueError(f'Missing video op {hex(vop)} = {vop}')
    vfunc(scf)


goblin_lookup = {
    0: 0,
    1: 1,
    2: 2,
    4: 3,
    5: 4,
    6: 5,
    7: 6,
    8: 7,
    9: 8,
    10: 9,
    12: 10,
    13: 71,
    14: 12,
    15: 13,
    16: 14,
    21: 15,
    22: 16,
    23: 17,
    24: 18,
    25: 19,
    26: 20,
    27: 21,
    28: 22,
    29: 23,
    30: 24,
    32: 25,
    33: 26,
    34: 27,
    35: 28,
    36: 29,
    37: 30,
    40: 31,
    41: 32,
    42: 33,
    43: 34,
    44: 35,
    50: 36,
    52: 37,
    53: 38,
    100: 39,
    152: 40,
    200: 41,
    201: 42,
    202: 43,
    203: 44,
    204: 45,
    250: 46,
    251: 47,
    252: 48,
    500: 49,
    502: 50,
    503: 51,
    600: 52,
    601: 53,
    602: 54,
    603: 55,
    604: 56,
    605: 57,
    1000: 58,
    1001: 59,
    1002: 60,
    1003: 61,
    1004: 62,
    1005: 63,
    1006: 64,
    1008: 65,
    1009: 66,
    1010: 67,
    1011: 68,
    1015: 69,
    2005: 70,
    3: 71,
}


def gob_o2_handleGoblins(scf):
    return [reads_uint16le(scf) * 4 for _ in range(6)]


goblin_ops = {
    0x00: xparam('o2_loadInfogramesIns'),
    0x01: cparam('o2_startInfogrames', reads_uint16le),
    0x02: cparam('o2_stopInfogrames', reads_uint16le),
    0x09: xparam('o2_playInfogrames'),
    0x27: lcparam('o2_handleGoblins', gob_o2_handleGoblins),
    0x47: xparam('o1_dummy'),
}


def o2_goblinFunc(scf):
    cmd = reads_uint16le(scf)
    _skip = scf.read(2)

    if cmd != 101:
        gfunc = goblin_ops.get(goblin_lookup[cmd])
        if gfunc is None:
            raise ValueError(f'Missing goblin op {hex(cmd)} = {cmd}')
        gfunc(scf)


def o1_loadTot(scf):
    size = reads_uint8(scf)

    fname = scf.read(size).decode('ascii') if size & 0x80 == 0 else read_expr(scf)
    printl('o1_loadTot', fname)


def o2_loadSound(scf):
    slot = read_expr(scf)
    id = read_uint16le(scf.read(2))
    if id == 65535:
        msg = scf.read(9).decode('ascii')
        printl('o2_loadSound', slot, msg.split('\0'))
    else:
        printl('o2_loadSound', slot, id)


def o1_repeatUntil(scf):
    printl('repeat {')
    func_block(scf, 1)
    scf.read(1)
    cond = read_expr(scf)
    printl(f'}} until ({cond})')


def o1_whileDo(scf):
    printl("while ({}) {{".format(read_expr(scf)))
    func_block(scf, 1)
    printl('}')


def o1_loadSpriteToPos(scf):
    printl(
        'o1_loadSpriteToPos',
        reads_uint16le(scf),
        read_expr(scf),
        read_expr(scf),
        reads_uint8(scf),
    )
    _skip = scf.read(1)


def o1_palLoad(scf):
    sub = ord(scf.read(1))
    masked = sub & 0x7F
    printl('o1_palLoad', int(sub & 0x80 != 0), masked)

    skip_count = {48: 48, 49: 18, 50: 16, 51: 2, 52: 48, 53: 2, 55: 2, 54: 0, 61: 4}

    _skip = scf.read(skip_count[masked])


def o1_if(scf):
    printl("if ({}) {{".format(read_expr(scf)))

    func_block(scf, 0)

    if (scf.read(1)[0] >> 4) == 12:
        printl('} else {')
        func_block(scf, 0)

    printl('}')


def o1_switch(scf):
    printl("switch ({}) {{".format(read_var_index(scf)))

    while True:
        ln = reads_uint8(scf)
        if ln == 251:
            break

        for _ in range(ln):
            printl('case {}:'.format(read_expr(scf)))

        func_block(scf, 0)

        printl(' ' * 4 + 'break')

    if (peek_uint8(scf) >> 4) == 4:
        printl('default:')
        _skip = scf.read(1)
        func_block(scf, 0)

        printl(' ' * 4 + 'break')

    printl('}')


def o2_printText(scf):
    params = (
        read_expr(scf),
        read_expr(scf),
        read_expr(scf),
        read_expr(scf),
        read_expr(scf),
    )

    expr = ' "'
    while True:
        while peek_uint8(scf) != ord('.') and peek_uint8(scf) != 200:
            expr += scf.read(1).decode()

        if peek_uint8(scf) != 200:
            scf.read(1)

            expr += '" '
            if peek_uint8(scf) in {16, 17, 18, 23, 24, 25, 26, 27, 28}:
                expr += read_var_index(scf)
            scf.read(1)
        else:
            expr += '"'

        if peek_uint8(scf) == 200:
            break

    scf.read(1)

    printl('o2_printText', ' '.join(str(x) for x in params) + expr)


def read_block(scf):
    something = scf.read(2)
    size = scf.read(2)
    next_pos = read_uint16le(size) - 2
    skipped = scf.read(next_pos)
    assert len(skipped) == next_pos, (len(skipped), next_pos)
    return something + size + skipped


def evaluate_new(scf):
    typ = scf.read(1)[0]
    print('TYP', typ)
    if typ & 0x40:
        typ -= 0x40
        num = scf.read(1)[0]
    if typ & 0x80:
        left = read_expr(scf)
        top = read_expr(scf)
        width = read_expr(scf)
        height = read_expr(scf)
    else:
        left = reads_uint16le(scf)
        top = reads_uint16le(scf)
        width = reads_uint16le(scf)
        height = reads_uint16le(scf)
    typ &= 0x7F
    print('HOTSPOT', typ, left, top, width, height)
    if typ in {11, 12}:
        _skip = scf.read(6)
        func_block(scf, 2)
        # _skipped = read_block(scf)
    elif typ in {0, 1}:
        _skip = scf.read(6)
        func_block(scf, 2)
        func_block(scf, 2)
        # _skipped = read_block(scf)
        # _skipped2 = read_block(scf)
    elif typ in {3, 4, 5, 6, 7, 8, 9, 10}:
        key = read_var_index(scf)
        font_index = reads_uint16le(scf)
        back_color, front_color = scf.read(2)
        if 5 <= typ <= 8:
            ln = reads_uint16le(scf)
            # func_block(scf, 2)
            _skipped = scf.read(ln)
        if typ & 1 == 0:
            func_block(scf, 2)
            # _skipped = read_block(scf)
    elif typ in {20, 2, 21}:
        key = reads_uint16le(scf)
        ids = reads_uint16le(scf)
        flags = reads_uint16le(scf)
        func_block(scf, 2)
        # _skipped = read_block(scf)
        # print(scf.tell(), _skipped)


def func_block(scf, ret_flag):
    # print('ENTER', scf, scf.tell(), ret_flag)

    block_start = scf.tell()

    block_type = scf.read(1)[0]
    cmd_count = scf.read(1)[0]

    if block_type == 2:
        ctx['indent'] += 1
        printl('hotspot {')
        handle_mouse, duration, leave_window, idx1, idx2, recalculate = scf.read(6)
        print(cmd_count)
        for i in range(cmd_count):
            evaluate_new(scf)
        # print(scf.read(1))

        ctx['indent'] -= 1
        return

    assert block_type == 1, block_type
    size = reads_uint16le(scf)

    if cmd_count == 0:
        return

    params = {
        'counter': 0,
        'ret_flag': ret_flag,
    }
    assert cmd_count > 0

    ctx['indent'] += 1

    while params['counter'] < cmd_count:
        # print('LOOP', scf, scf.tell(), ret_flag)

        cmd_t = reads_uint8(scf)
        cmd = cmd_t

        if (cmd >> 4) >= 12:
            cmd2 = 16 - (cmd >> 4)
            cmd &= 0xF
        else:
            cmd2 = 0

        params['counter'] += 1

        if cmd2 == 0:
            cmd >>= 4

        cmd_u = cmd2 * 16 + cmd
        assert cmd2 <= 4 and cmd <= 15, (cmd2, cmd)

        # begin = scf.tell()
        # print('BEGIN', begin + 128)

        opcode(scf, cmd_u, params)

        # end = scf.tell()
        # scf.seek(begin)
        # print('END', end + 128, scf.read(end - begin))
        # scf.seek(end)

    assert scf.tell() - block_start == size + 2, (scf.tell() - block_start, size + 2)
    ctx['indent'] -= 1


def text_hint(ctx, textid):
    res = ctx['texts'][textid]
    lang = ctx.get('lang')
    if lang is not None:
        return res[lang]
    return res


def o1_printTotText(scf):
    textid = reads_uint16le(scf)
    printl('o1_printTotText', textid, '//', text_hint(ctx, textid))


def o2_getTotTextItemPart(scf):
    textid = reads_uint16le(scf)
    var_string = read_var_index(scf)
    part = read_expr(scf)
    printl(f'{var_string} = o2_getTotTextItemPart', textid, part, '//', text_hint(ctx, textid))


gob1_ops = {
    0x00: gparam('o1_callSub'),
    0x01: gparam('o1_callSub'),
    0x02: gparam('o1_printTotText'),
    0x03: fparam('o1_loadCursor', reads_uint16le, reads_uint8),
    0x05: gparam('o1_switch'),
    0x06: gparam('o1_repeatUntil'),
    0x07: gparam('o1_whileDo'),
    0x08: gparam('o1_if'),
    0x09: xparam('o1_assign'),
    0x0A: gparam('o1_loadSpriteToPos'),
    0x11: xparam('o1_printText'),
    0x12: gparam('o1_loadTot'),
    0x13: gparam('o1_palLoad'),
    0x14: fparam('o1_keyFunc', reads_uint16le),
    0x15: fparam('o1_capturePush', read_expr, read_expr, read_expr, read_expr),
    0x16: fparam('o1_capturePop'),
    0x17: xparam('o1_animPalInit'),
    0x1E: gparam('o1_drawOperations'),
    0x1F: xparam('o1_setcmdCount'),
    0x20: fparam('o1_return'),
    0x21: fparam('o1_renewTimeInVars'),
    0x22: fparam('o1_speakerOn', read_expr),
    0x23: fparam('o1_speakerOff'),
    0x24: xparam('o1_putPixel'),
    0x25: xparam('o1_goblinFunc'),
    0x26: fparam(
        'o1_createSprite',
        reads_uint16le,
        reads_uint16le,
        reads_uint16le,
        reads_uint16le,
    ),
    0x27: fparam('o1_freeSprite', reads_uint16le),
    0x30: fparam('o1_returnTo'),
    0x31: fparam(
        'o1_loadSpriteContent', reads_uint16le, reads_uint16le, reads_uint16le
    ),
    0x32: xparam('o1_copySprite'),
    0x33: fparam(
        'o1_fillRect',
        reads_uint16le,
        read_expr,
        read_expr,
        read_expr,
        read_expr,
        read_expr,
    ),
    0x34: fparam(
        'o1_drawLine',
        reads_uint16le,
        read_expr,
        read_expr,
        read_expr,
        read_expr,
        read_expr,
    ),
    0x35: fparam('o1_strToLong', read_var_index, read_var_index),
    0x36: xparam('o1_invalidate'),
    0x37: fparam('o1_setBackDelta', read_expr, read_expr),
    0x38: fparam('o1_playSound', read_expr, read_expr, read_expr),
    0x39: xparam('o1_stopSound'),
    0x3A: xparam('o1_loadSound'),
    0x3B: fparam('o1_freeSoundSlot', read_expr),
    0x3C: xparam('o1_waitEndPlay'),
    0x3D: xparam('o1_playComposition'),
    0x3E: xparam('o1_getFreeMem'),
    0x3F: xparam('o1_checkData'),
    0x41: xparam('o1_cleanupStr'),
    0x42: xparam('o1_insertStr'),
    0x43: xparam('o1_cutStr'),
    0x44: xparam('o1_strstr'),
    0x45: fparam('o1_istrlen', read_var_index, read_var_index),
    0x46: fparam('o1_setMousePos', read_expr, read_expr),
    0x47: fparam('o1_setFrameRate', read_expr),
    0x48: fparam('o1_animatePalette'),
    0x49: fparam('o1_animateCursor'),
    0x4A: fparam('o1_blitCursor'),
    0x4B: fparam('o1_loadFont', read_expr, reads_uint16le),
    0x4C: fparam('o1_freeFont', reads_uint16le),
    0x4D: xparam('o1_readData'),
    0x4E: xparam('o1_writeData'),
    0x4F: fparam('o1_manageDataFile', read_expr),
}

gob2_ops = {
    **gob1_ops,
    0x09: gparam('o2_assign'),
    0x11: gparam('o2_printText'),
    0x17: fparam('o2_animPalInit', reads_uint16le, read_expr, read_expr),
    0x18: xparam('o2_addHotspot'),
    0x19: xparam('o2_removeHotspot'),
    0x1A: gparam('o2_getTotTextItemPart'),
    0x25: gparam('o2_goblinFunc'),
    0x39: fparam('o2_stopSound', read_expr),
    0x3A: gparam('o2_loadSound'),
    0x3E: fparam('o2_getFreeMem', read_var_index, read_var_index),
    0x3F: fparam('o2_checkData', read_expr, read_var_index),
    0x4D: fparam('o2_readData', read_expr, read_var_index, read_expr, read_expr),
    0x4E: fparam('o2_writeData', read_expr, read_var_index, read_expr, read_expr),
}

gob3_ops = {
    **gob2_ops,
    0x32: fparam(
        'o3_copySprite',
        reads_uint16le,
        reads_uint16le,
        read_expr,
        read_expr,
        read_expr,
        read_expr,
        read_expr,
        read_expr,
        reads_uint16le,
    ),
}

    gob3_ops,
    0x44: xparam('o4_draw0x44'),
    0x45: xparam('o4_draw0x45'),
    0x80: fparam('o4_playVmdOrMusic', reads_uint16le, read_expr, read_expr),
    0x88: xparam('o4_draw0x8C'),
    0x90: xparam('o4_draw0x90'),
    0xA0: xparam('o4_draw0xA1'),
    0xA0: xparam('o4_draw0xA2'),
    0xA4: fparam('o4_draw0xA4', read_expr),
    0x54: xparam('o4_draw0x57'),
}

gob5_ops = {
    gob4_ops,
    0x60: xparam('o5_deleteFile'),
    0x44: xparam('o5_istrlen'),
    0x00: fparam('o5_spaceShooter', reads_uint16le, read_expr, read_expr),
    0x00: xparam('o5_getSystemCDSpeed'),
    0x00: xparam('o5_getSystemRAM'),
    0x00: xparam('o5_getSystemCPUSpeed'),
    0x04: xparam('o5_getSystemDrawSpeed'),
    0x04: fparam('o5_totalSystemSpecs', read_expr),
    0x04: xparam('o5_saveSystemSpecs'),
    0x04: fparam('o5_loadSystemSpecs', read_var_index, read_var_index),
    0x08: fparam('o5_gob92', read_expr, read_var_index),
    0x08: fparam('o5_gob95', read_expr, read_var_index, read_expr, read_expr),
    0x08: fparam('o5_gob96', read_expr, read_var_index, read_expr, read_expr),
    0x08: fparam('o5_gob97', read_expr, read_var_index, read_expr, read_expr),
    0x0C: fparam('o5_gob98', read_expr, read_var_index, read_expr, read_expr),
    0x0C: fparam('o5_gob100', read_expr, read_var_index, read_expr, read_expr),
    0x0C: fparam('o5_gob200', read_expr, read_var_index, read_expr, read_expr),
}

gob6_ops = {
    gob5_ops,
    0x00: xparam('o6_loadCursor'),
    0x08: xparam('o6_assign'),
    0x24: fparam('o6_createSprite', reads_uint16le, read_expr, read_expr),
}

gob7_ops = {
    gob6_ops,
    0x44: xparam('o7_displayWarning'),
    0x44: xparam('o7_logString'),
    0x54: fparam('o7_intToString', reads_uint16le, read_expr, read_expr),
    0x58: fparam('o7_callFunction', reads_uint16le, read_expr, read_expr),
    0x58: fparam('o7_loadFunctions', reads_uint16le, read_expr, read_expr),
    0x60: fparam('o7_copyFile', reads_uint16le, read_expr, read_expr),
    0x60: fparam('o7_moveFile', reads_uint16le, read_expr, read_expr),
    0x88: fparam('o7_draw0x89', reads_uint16le, read_expr, read_expr),
    0x88: fparam('o7_findFile', reads_uint16le, read_expr, read_expr),
    0x88: fparam('o7_findCDFile', reads_uint16le, read_expr, read_expr),
    0x8C: fparam('o7_getSystemProperty', reads_uint16le, read_expr, read_expr),
    0x90: fparam('o7_loadImage', reads_uint16le, read_expr, read_expr),
    0x90: fparam('o7_setVolume', reads_uint16le, read_expr, read_expr),
    0x94: fparam('o7_zeroVar', reads_uint16le, read_expr, read_expr),
    0xA0: fparam('o7_getINIValue', reads_uint16le, read_expr, read_expr),
    0xA0: fparam('o7_setINIValue', reads_uint16le, read_expr, read_expr),
    0xA4: fparam('o7_loadIFFPalette', reads_uint16le, read_expr, read_expr),
    0xC4: fparam('o7_opendBase', reads_uint16le, read_expr, read_expr),
    0xC4: fparam('o7_closedBase', reads_uint16le, read_expr, read_expr),
    0xC4: fparam('o7_getDBString', reads_uint16le, read_expr, read_expr),
    0x00: fparam('o7_loadCursor', reads_uint16le, read_expr, read_expr),
    0x4C: fparam('o7_readData', reads_uint16le, read_expr, read_expr),
    0x44: fparam('o7_oemToANSI', reads_uint16le, read_expr, read_expr),
    0x44: fparam('o7_gob0x201', reads_uint16le, read_expr, read_expr),

}

named_variables = {
    'var8_4931': 'g_Language',
}


def opcode(scf, cmd, params):
    ctx['offset'] = scf.tell()
    func = gob3_ops[cmd]
    # print(cmd, hex(cmd), func)
    func(scf)
    ctx['offset'] = scf.tell()


ctx = {
    'offset': 0,
    'indent': 0,
}


def printl(*msgs):
    offset = ctx['offset']
    indent = ctx['indent']
    indent = ' ' * 4 * indent
    pref = ''
    pref = f'[{128 + offset:08d}]:'
    print(pref + indent, *msgs)


def read_ext_item(items, index, ext_data, com_data):
    offset, size, width, height, packed = items[index]
    if offset < 0:
        print('NEGATIVE OFFSET')
        if com_data is None:
            raise ValueError('No commun data')
        # TODO: handle different COMMUN.EX file for different TOTs
        with io.BytesIO(com_data) as cstream:
            assert ~offset == -(offset + 1)
            cstream.seek(~offset)
            if packed:
                uncompressed_size = reads_uint32le(cstream)
                return unpack_chunk(cstream, uncompressed_size)
            else:
                return cstream.read(size)
    else:
        with io.BytesIO(ext_data) as stream:
            stream.seek(offset)
            if packed:
                uncompressed_size = reads_uint32le(stream)
                return unpack_chunk(stream, uncompressed_size)
            else:
                return stream.read(size)


def menu():
    import argparse

    parser = argparse.ArgumentParser(description='extract pak archive')
    parser.add_argument('directory', help='game directory to work on')
    parser.add_argument(
        'totfiles',
        nargs='*',
        default=['*.TOT'],
        help='script to decompile',
    )
    parser.add_argument(
        '--lang',
        '-l',
        help='language to focus on message hints',
    )
    parser.add_argument(
        '--keys',
        '-k',
        action='store_true',
        help='replace text by keyboard key position',
    )
    parser.add_argument(
        '--exported',
        '-e',
        action='store_true',
        help='only decompile exported functions',
    )


    return parser.parse_args()


def main(gamedir, rebuild, scripts, lang=None, keys=False, exported=False):
    game = archive.open_game(gamedir)

    decoders = defaultdict(lambda: CodePageEncoder('cp850'))
    decoders['ISR'] = CodePageEncoder('windows-1255')
    decoders['KOR'] = CodePageEncoder('utf-8', errors='surrogateescape')

    if keys:
        decoders['ISR'] = HebrewKeyReplacer

    if rebuild:
        raise ValueError('Recompiler was not implemented yet')

    com_data = {}
    com_entry = None
    for com_pattern, com_entry in game.search(['COMMUN.EX*']):
        com_data[com_entry.name] = com_entry.read_bytes()

    ctx['com_data'] = com_data
    ctx['com_entry'] = com_entry

    script_dir = Path('scripts')
    os.makedirs(script_dir, exist_ok=True)

    for pattern, entry in game.search(scripts):

        print(f'Decompiling {entry.name}...')
        texts_data = None
        with entry.open('rb') as tot_file:
            script, functions, texts_data, res_data = read_tot(tot_file)

        tot_file = entry.read_bytes()

        for ext_pattern, ext_entry in game.search([entry.with_suffix('.EXT').name]):
            with ext_entry.open('rb') as ext_file:
                ctx['ext_items'] = list(read_ext_table(ext_file))
                ctx['ext_data'] = ext_file.read()

        ctx['texts'] = dict(
            enumerate(
                {lang: decrypt(decoders, line, lang) for lang in line}
                for line in tot.write_parsed(game, entry)
            )
        )

        ctx['lang'] = lang

        # print(ext_items)

        # print(functions)
        ctx['functions'] = [x for x in functions if x >= 128 and x != 0xFFFF]

        def on_functions(scfa):
            seen = set()
            for func in ctx['functions']:
                if func in seen:
                    continue
                scfa.seek(func - 128)
                yield
                seen.add(func)

        def on_all_file(scfa):
            while scfa.tell() + 1 < len(script):
                yield

        script_out = script_dir / f'{entry.name}.txt'
        with (script_out).open('w', encoding='utf-8') as outstream:
            with redirect_stdout(outstream):
                print(ctx['functions'])
                with io.BytesIO(script) as scfa:
                    works_on = on_functions(scfa) if exported else on_all_file(scfa)
                    for _ in works_on:
                        ctx['offset'] = scfa.tell()
                        printl(f'sub_{scfa.tell() + 128} {{')
                        func_block(scfa, 2)
                        printl('}')
                        print()


if __name__ == '__main__':
    args = menu()

    main(
        args.directory,
        False,
        args.totfiles,
        args.lang,
        args.keys,
        args.exported,
    )
