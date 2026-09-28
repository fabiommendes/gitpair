"""Textual app to review the plan and answer its questions."""

from __future__ import annotations

from rich.markup import escape
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Header, Label, OptionList
from textual.widgets.option_list import Option

from gitpair.plan import Action, Item, Plan, describe

COLUMNS = ("Repository", "Branch", "Status", "Action")


class ChoiceScreen(ModalScreen[Action | None]):
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

    def __init__(self, item: Item, plan: Plan):
        super().__init__()
        self.item = item
        self.plan = plan

    def compose(self) -> ComposeResult:
        names = self.plan.local.name, self.plan.remote.name
        with Vertical():
            yield Label(f"[b]{self.item.repo}[/b]  {escape(self.item.status)}")
            yield OptionList(
                *(Option(action.describe(*names)) for action in self.item.options)
            )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(self.item.options[event.option_index])


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
        for column in COLUMNS:
            table.add_column(column, key=column)
        for item in self.items.values():
            table.add_row(
                item.repo,
                item.branch or "-",
                escape(item.status),
                self.label(item),
                key=item.repo,
            )
        self.refresh_title()

    def label(self, item: Item) -> str:
        if item.choice is None:
            return "[b yellow]? decide[/]"
        text = escape(describe(item, self.plan.local.name, self.plan.remote.name))
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

    def choose(self, item: Item, action: Action | None) -> None:
        if action is None:
            return
        item.choice = action
        self.query_one(DataTable).update_cell(item.repo, "Action", self.label(item))
        self.refresh_title()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        item = self.items[str(event.row_key.value)]
        if len(item.options) > 1:
            self.push_screen(
                ChoiceScreen(item, self.plan), lambda action: self.choose(item, action)
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
