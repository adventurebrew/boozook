import argparse
from dataclasses import dataclass
from operator import itemgetter
import pathlib

from prompt_toolkit import PromptSession
from boozook import archive, font
from boozook import text
from boozook import graphics
from boozook.prompt import Option, select_prompt


def decompile_scripts(gamedir, **kwargs):
    print('decompile_scripts', gamedir, kwargs)


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
    lang = session.prompt('Which language to focus on message hint: ')
    keys = ctx.get('keys', None)
    if keys is None:
        keys = select_prompt(
            'Check to apply:', [Option('keys', 'Replace keys by keyboard position')]
        )
    return {
        'lang': lang or None,
        'keys': bool(keys),
    }


@dataclass
class ProgramArgs:
    gamedir: pathlib.Path
    resources: dict[str, dict]
    rebuild: bool


def menu():
    parser = argparse.ArgumentParser(
        description='A tool to modify Coktel Vision games.'
    )
    parser.add_argument(
        'path',
        nargs='?',
        default='.',
        help='The path to the game directory. If omitted, current working directory is used.',
    )
    parser.add_argument(
        '--texts',
        '-t',
        action='store_true',
        help='Extract or inject texts.',
    )

    parser.add_argument(
        '--allowed',
        '-i',
        action='append',
        help='allow only specific patterns to be modified',
    )
    parser.add_argument(
        '--keys',
        '-k',
        action='store_true',
        help='replace text by keyboard key position',
    )

    parser.add_argument(
        '--graphics',
        '-g',
        action='store_true',
        help='Extract or inject graphics.',
    )
    parser.add_argument(
        '--archive',
        '-a',
        action='store_true',
        help='Extract or rebuild game archives.',
    )

    parser.add_argument(
        '--patterns',
        '-p',
        nargs='*',
        default=archive.ARCHIVE_PATTERNS,
        help='game directory with files to extract',
    )

    parser.add_argument(
        '--fonts',
        '-f',
        action='store_true',
        help='Extract or inject fonts.',
    )
    # parser.add_argument(
    #     '--scripts',
    #     '-s',
    #     action='store_true',
    #     help='Decompile game scripts.',
    # )

    # parser.add_argument(
    #     '--lang',
    #     '-l',
    #     help='language to show texts in',
    # )

    parser.add_argument(
        '-r', '--rebuild', action='store_true', help='Rebuild or inject resources.'
    )
    args = parser.parse_args()

    gamedir = pathlib.Path(args.path)

    options = vars(args)
    options.pop('path')
    if not any(
        itemgetter(
            'texts',
            'graphics',
            'fonts',
            'archive',
            # 'scripts',
        )(options)
    ):
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
                # Option('scripts', 'Scripts*', advanced=scripts_advanced),
            ]
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
            resources[option.key] = (
                option.advanced(ctx) if option.advanced is not None else {}
            )
            ctx.update(resources[option.key])
        return ProgramArgs(
            gamedir=gamedir,
            resources=resources,
            rebuild=selected_action.key == 'inject',
        )

    # Options given, run non-interactively
    resources = {}
    if args.archive:
        resources['archive'] = {'patterns': args.patterns}
    if args.fonts:
        resources['fonts'] = {}
    if args.texts:
        resources['texts'] = {
            'allowed': args.allowed or (),
            'keys': args.keys,
        }
    if args.graphics:
        resources['graphics'] = {}
    # if args.scripts:
    #     resources['scripts'] = {
    #         'lang': args.lang,
    #         'keys': args.keys,
    #     }
    return ProgramArgs(gamedir=gamedir, resources=resources, rebuild=args.rebuild)


def main():
    args = menu()

    gamedir = args.gamedir

    for resource, advanced in args.resources.items():
        if resource == 'archive':
            archive.main(
                gamedir,
                extract=not args.rebuild,
                compress=args.rebuild,
                **advanced,
            )
        elif resource == 'fonts':
            font.main(gamedir, args.rebuild, **advanced)
        elif resource == 'texts':
            text.main(gamedir, args.rebuild, **advanced)
        elif resource == 'graphics':
            graphics.main(gamedir, args.rebuild, **advanced)
        elif resource == 'scripts':
            decompile_scripts(gamedir, args.rebuild, **advanced)
        else:
            raise ValueError(repr(resource))

        if args.rebuild:
            gamedir = pathlib.Path('patch')


if __name__ == '__main__':
    main()
