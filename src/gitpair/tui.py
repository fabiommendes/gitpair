"""Textual app to review the plan and answer its questions."""

from __future__ import annotations

from rich.markup import escape
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Header, Label, OptionList
from textual.widgets.option_list import Option

from gitpair.plan import Action, FilesPolicy, Item, Plan, count, icons

COLUMNS = ("Repository", "Branch", "Status", "Action")

#: Either question a :class:`ChoiceScreen` can ask: the git action, or, when
#: an item has file conflicts, what to do with them.
Choice = Action | FilesPolicy


class ChoiceScreen(ModalScreen[Choice | None]):
    """A modal asking the user to pick one of ``choices``.

    Used both for an item's git action and, when it has file conflicts, for
    its :class:`~gitpair.plan.FilesPolicy`: two separate questions rather
    than one combined option list, to keep each answer's text short.
    """

    BINDINGS = [Binding("escape", "dismiss(None)", "Cancel")]
    DEFAULT_CSS = """
    ChoiceScreen { align: center middle; }
    ChoiceScreen > Vertical {
        width: 80; height: auto; padding: 1 2;
        border: thick $accent; background: $surface;
    }
    ChoiceScreen Label { margin-bottom: 1; }
    ChoiceScreen OptionList { height: auto; }
    """

    def __init__(self, header: str, choices: list[tuple[Choice, str]]):
        super().__init__()
        self.header = header
        self.choices = choices

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self.header)
            yield OptionList(*(Option(text) for _, text in self.choices))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(self.choices[event.option_index][0])


def _action_choices(item: Item, plan: Plan) -> list[tuple[Choice, str]]:
    names = plan.local.name, plan.remote.name
    return [(action, action.describe(*names)) for action in item.options]


def _action_header(item: Item) -> str:
    return f"[b]{escape(item.repo)}[/b]  {escape(item.status)}"


def _policy_choices() -> list[tuple[Choice, str]]:
    return [(policy, policy.describe()) for policy in FilesPolicy]


def _policy_header(item: Item) -> str:
    conflicts = count(item.file_conflicts, "file")
    return f"[b]{escape(item.repo)}[/b]  {conflicts} differ on both hosts"


class PlanApp(App[bool]):
    """Returns True when the user asks to run the plan."""

    TITLE = "gitpair"
    BINDINGS = [
        Binding("s", "skip", "Skip"),
        Binding("a", "accept", "Accept first option"),
        Binding("x", "run", "Run plan"),
        Binding("q", "quit_plan", "Quit"),
    ]

    def __init__(self, plan: Plan):
        super().__init__()
        self.plan = plan
        self.items = {item.repo: item for item in plan.pending}

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(cursor_type="row", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = f"{self.plan.local.name} (here) <-> {self.plan.remote.name}"
        table = self.query_one(DataTable)
        table.add_column("", key="icon")
        for column in COLUMNS:
            table.add_column(column, key=column)
        for item in self.items.values():
            status_icon, status, _, _ = self._icons(item)
            table.add_row(
                status_icon,
                escape(item.repo),
                escape(item.branch or "-"),
                escape(status),
                self.label(item),
                key=item.repo,
            )
        self.refresh_title()

    def _icons(self, item: Item) -> tuple[str, str, str, str]:
        return icons(item, self.plan.local.name, self.plan.remote.name)

    def label(self, item: Item) -> str:
        _, _, action_icon, action_text = self._icons(item)
        text = escape(f"{action_icon} {action_text}")
        if item.needs_decision:
            return f"[b yellow]{text}[/]"
        return f"[dim]{text}[/]" if item.choice is Action.SKIP else text

    def refresh_title(self) -> None:
        open_ = sum(item.needs_decision for item in self.items.values())
        synced = len(self.plan.items) - len(self.items)
        self.title = f"gitpair: {open_} to decide, {synced} in sync"

    def current(self) -> Item | None:
        table = self.query_one(DataTable)
        if not table.row_count:
            return None
        key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        return self.items[str(key.value)]

    def choose(self, item: Item, choice: Choice | None) -> None:
        """Apply ``choice``, then ask about file conflicts too if it is still open.

        A row with conflicting files is asked twice: once for the git
        action, once for the :class:`~gitpair.plan.FilesPolicy`, chained
        through this method's own callback.
        """
        if choice is None:
            return
        if isinstance(choice, Action):
            item.choice = choice
        else:
            item.files_policy = choice
        if isinstance(choice, Action) and item.needs_decision:
            self.push_screen(
                ChoiceScreen(_policy_header(item), _policy_choices()),
                lambda answer: self.choose(item, answer),
            )
            return
        self.query_one(DataTable).update_cell(item.repo, "Action", self.label(item))
        self.refresh_title()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        item = self.items[str(event.row_key.value)]
        if len(item.options) > 1:
            self.push_screen(
                ChoiceScreen(_action_header(item), _action_choices(item, self.plan)),
                lambda choice: self.choose(item, choice),
            )

    def action_skip(self) -> None:
        if item := self.current():
            self.choose(item, Action.SKIP)

    def action_accept(self) -> None:
        if item := self.current():
            self.choose(item, item.options[0])

    def action_run(self) -> None:
        self.exit(True)

    def action_quit_plan(self) -> None:
        self.exit(False)
