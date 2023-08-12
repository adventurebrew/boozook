from dataclasses import dataclass
from typing import Callable, List, Optional, TypeVar, Union

from prompt_toolkit.application import Application
from prompt_toolkit.filters import IsDone
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import ConditionalContainer, HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.layout import Layout


AdvancedT = TypeVar('AdvancedT')


@dataclass
class Option:
    key: str
    label: Optional[str] = None
    selected: bool = False
    advanced: Optional[Callable[[], AdvancedT]] = None


@dataclass
class SelectedOption:
    key: str
    advanced: Optional[Callable[[], dict]] = None


class SelectControl(FormattedTextControl):
    def __init__(self, options: List[Option], multi_select: bool = True):
        self.options = options
        self.selected_index = 0
        self.multi_select = multi_select
        self.selected_keys: set = {option.key for option in options if option.selected}
        self.advanced_keys: set = set()
        super().__init__(key_bindings=self._create_key_bindings())

    @property
    def selected_option(self) -> Option:
        return self.options[self.selected_index]

    def _create_key_bindings(self) -> KeyBindings:
        kb = KeyBindings()
        count = len(self.options)

        @kb.add('down', eager=True)
        def move_cursor_down(event):
            self.selected_index = (self.selected_index + 1) % count

        @kb.add('up', eager=True)
        def move_cursor_up(event):
            self.selected_index = (self.selected_index - 1) % count

        if self.multi_select:

            @kb.add('space', eager=True)
            def toggle_select(event):
                option = self.selected_option
                if option.key in self.selected_keys:
                    self.selected_keys.remove(option.key)
                else:
                    self.selected_keys.add(option.key)

            @kb.add('a', eager=True)
            def toggle_advanced(event):
                option = self.selected_option
                if option.advanced is not None and option.key in self.selected_keys:
                    if option.key in self.advanced_keys:
                        self.advanced_keys.remove(option.key)
                    else:
                        self.advanced_keys.add(option.key)

        @kb.add('enter', eager=True)
        def set_selected(event):
            if self.multi_select:
                selected_options = [
                    SelectedOption(
                        option.key,
                        advanced=option.advanced
                        if option.key in self.advanced_keys
                        else None,
                    )
                    for option in self.options
                    if option.key in self.selected_keys
                ]
                event.app.exit(result=selected_options)
            else:
                selected_option = SelectedOption(
                    self.selected_option.key,
                    advanced=self.selected_option.advanced,
                )
                event.app.exit(result=selected_option)

        @kb.add('c-q', eager=True)
        @kb.add('c-c', eager=True)
        def _(event):
            raise KeyboardInterrupt()

        return kb

    def select_option_text(self, mark: str) -> List[tuple]:
        text = []
        for idx, op in enumerate(self.options):
            display_text = op.label or op.key
            if self.multi_select:
                if op.key in self.selected_keys:
                    if op.key in self.advanced_keys:
                        line = f'[+] {display_text} (Advanced)\n'
                    else:
                        line = f'[+] {display_text}\n'
                else:
                    line = f'[ ] {display_text}\n'
            else:
                line = f'{display_text}\n'
            prefix = mark if idx == self.selected_index else ' ' * len(mark)
            line = f'{prefix} {line}'
            text.append(('', line))  # style, string
        return text


def select_prompt(
    message: str,
    options: List[Option],
    mark: str = '>',
    multi_select: bool = True,
) -> Union[List[SelectedOption], SelectedOption]:
    control = SelectControl(options, multi_select=multi_select)

    def get_formatted_text() -> List[tuple]:
        return control.select_option_text(mark)

    layout = Layout(
        HSplit(
            [
                Window(
                    height=Dimension.exact(1),
                    content=FormattedTextControl(
                        lambda: message + '\n',
                        show_cursor=False,
                    ),
                ),
                Window(
                    height=Dimension.exact(len(control.options)),
                    content=FormattedTextControl(get_formatted_text),
                ),
                ConditionalContainer(
                    Window(control),
                    filter=~IsDone(),
                ),
            ]
        )
    )

    app = Application(
        layout=layout,
        key_bindings=control.key_bindings,
        full_screen=False,
    )
    return app.run()
