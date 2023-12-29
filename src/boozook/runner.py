import argparse
import sys
from dataclasses import dataclass
from operator import itemgetter
import pathlib

from prompt_toolkit import PromptSession
from boozook import archive, font
from boozook import text
from boozook import graphics
from boozook.codex import decomp_tot
from boozook.prompt import Option, select_prompt


def archive_advanced(ctx: dict) -> dict:
    session = PromptSession()
    patterns = session.prompt(
        'Enter patterns for files to extract separated by space (e.g. *.ITK *.STK): '
    )
    return {'patterns': patterns.split() if patterns else archive.ARCHIVE_PATTERNS}


def texts_advanced(ctx: dict) -> dict:
    session = PromptSession()
    allowed = session.prompt(
        'Enter which patterns are allowed to be modified separated by space (e.g. *.ISR *.CAT): '
    )
    keys = ctx.get('keys', None)
    if keys is None:
        keys = select_prompt(
            'Check to apply:', [Option('keys', 'Replace keys by keyboard position')]
        )
    return {
        'allowed': allowed.split() if allowed else (),
        'keys': bool(keys),
    }


def scripts_advanced(ctx: dict) -> dict:
    session = PromptSession()
    scripts = session.prompt(
        'Enter which scripts to decompile separated by space (e.g. *.TOT): '
    )
    lang = session.prompt('Which language to focus on message hint: ')
    keys = ctx.get('keys', None)
    if keys is None:
        keys = select_prompt(
            'Check to apply:', [Option('keys', 'Replace keys by keyboard position')]
        )
    exported = select_prompt(
        'Check to apply:', [Option('exported', 'Only decompile exported functions')]
    )
    return {
        'scripts': scripts.split() if scripts else ['*.TOT'],
        'lang': lang or None,
        'keys': bool(keys),
        'exported': bool(exported),
    }


@dataclass
class ProgramArgs:
    gamedir: pathlib.Path
    resources: dict[str, dict]
    rebuild: bool


def interactive_menu(gamedir, experimental=False):
    # No options given, run interactively
    action_options = [Option('extract', 'Extract'), Option('inject', 'Inject')]
    selected_action = select_prompt(
        'Would you like to extract or inject?', action_options, multi_select=False
    )
    if selected_action.key == 'extract':
        extract_options = [
            Option('archive', 'Archives*', advanced=archive_advanced),
            Option('fonts', 'Fonts', selected=True),
            Option('texts', 'Texts*', selected=True, advanced=texts_advanced),
            Option('graphics', 'Graphics'),
        ]
        if experimental:
            extract_options.append(
                Option('scripts', 'Scripts*', advanced=scripts_advanced, default={'scripts': ['*.TOT']})
            )
        selected_options = select_prompt(
            'Select resources to extract: (press A to select advanced options for entries with *)',
            extract_options,
        )
    elif selected_action.key == 'inject':
        inject_options = [
            Option('archive', 'Archives*'),
            Option('fonts', 'Fonts', selected=True),
            Option('texts', 'Texts*', selected=True, advanced=texts_advanced),
            Option('graphics', 'Graphics'),
        ]
        selected_options = select_prompt(
            'Select resources to inject: (press A to select advanced options for entries with *)',
            inject_options,
        )
    resources = {}
    ctx = {}
    for option in selected_options:
        ctx.update(option.default)
        resources[option.key] = (
            option.advanced(ctx) if option.advanced is not None else option.default
        )
        ctx.update(resources[option.key])
    return ProgramArgs(
        gamedir=gamedir,
        resources=resources,
        rebuild=selected_action.key == 'inject',
    )


def menu(argv=None):

    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        description='A tool to modify Coktel Vision games.'
    )

    experimental = '--experimental' in argv

    parser.add_argument(
        '--experimental',
        action='store_true',
        help='Enable experimental features.',
    )

    parser.add_argument(
        'path',
        nargs='?',
        default='.',
        help='The path to the game directory. If omitted, current working directory is used.',
    )
    parser.add_argument(
        '-t',
        '--texts',
        action='store_true',
        help='Extract or inject texts.',
    )

    parser.add_argument(
        '-i',
        '--allowed',
        action='append',
        help='allow only specific patterns to be modified',
    )
    parser.add_argument(
        '-k',
        '--keys',
        action='store_true',
        help='replace text by keyboard key position',
    )

    parser.add_argument(
        '-g',
        '--graphics',
        action='store_true',
        help='Extract or inject graphics.',
    )
    parser.add_argument(
        '-a',
        '--archive',
        action='store_true',
        help='Extract or rebuild game archives.',
    )

    parser.add_argument(
        '-p',
        '--patterns',
        nargs='*',
        default=archive.ARCHIVE_PATTERNS,
        help='game directory with files to extract',
    )

    parser.add_argument(
        '-f',
        '--fonts',
        action='store_true',
        help='Extract or inject fonts.',
    )

    if experimental:
        parser.add_argument(
            '-s',
            '--scripts',
            nargs='*',
            default=[] if {'-s', '--scripts'} & set(argv) else None,
            help='(experimental) Decompile game scripts.',
        )

        parser.add_argument(
            '-l',
            '--lang',
            help='(experimental) Language to focus on message hints in decompiled scripts.',
        )

        parser.add_argument(
            '-e',
            '--exported',
            action='store_true',
            help='(experimental) Only decompile exported functions.',
        )

    parser.add_argument(
        '-r',
        '--rebuild',
        action='store_true',
        help='Rebuild or inject resources.',
    )
    args = parser.parse_args(argv)

    gamedir = pathlib.Path(args.path)

    options = vars(args)
    options.pop('path')

    if options.get('scripts') == []:
        options['scripts'] = ['*.TOT']

    features = ('texts', 'graphics', 'archive', 'fonts')
    if experimental:
        features += ('scripts',)
    if not any(itemgetter(*features)(options)):
        return interactive_menu(gamedir, experimental=experimental)

    # Options given, run non-interactively
    resources = {}
    if args.archive:
        resources['archive'] = {'patterns': args.patterns}
    if args.texts:
        resources['texts'] = {
            'allowed': args.allowed or (),
            'keys': args.keys,
        }
    if args.fonts:
        resources['fonts'] = {}
    if args.graphics:
        resources['graphics'] = {}
    if experimental and args.scripts:
        resources['scripts'] = {
            'lang': args.lang,
            'keys': args.keys,
            'scripts': args.scripts,
            'exported': args.exported,
        }
    return ProgramArgs(
        gamedir=gamedir,
        resources=resources,
        rebuild=args.rebuild,
    )


def main():
    args = menu()

    gamedir = args.gamedir

    for resource, advanced in args.resources.items():
        if resource == 'archive':
            archive.main(gamedir, args.rebuild, **advanced)
        elif resource == 'fonts':
            font.main(gamedir, args.rebuild, **advanced)
        elif resource == 'texts':
            text.main(gamedir, args.rebuild, **advanced)
        elif resource == 'graphics':
            graphics.main(gamedir, args.rebuild, **advanced)
        elif resource == 'scripts':
            decomp_tot.main(gamedir, args.rebuild, **advanced)
        else:
            raise ValueError(repr(resource))

        if args.rebuild:
            gamedir = pathlib.Path('.')


if __name__ == '__main__':
    main()
