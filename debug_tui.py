"""Run this first to verify Textual keyboard input works in your terminal.
   uv run python debug_tui.py
   Expected: typing updates the log, Enter shows 'SUBMITTED', Ctrl+C quits.
"""
from textual.app import App, ComposeResult
from textual.widgets import Input, RichLog, Static


class DebugApp(App):
    CSS = """
    Screen { layout: vertical; }
    #log   { height: 1fr; border: round green; padding: 0 1; }
    #info  { height: 1; background: $surface-darken-1; padding: 0 1; }
    Input  { height: 3; }
    """

    def compose(self) -> ComposeResult:
        yield RichLog(id="log")
        yield Static("Waiting for keys...", id="info")
        yield Input(placeholder="type here then press Enter", id="inp")

    def on_mount(self) -> None:
        self.query_one("#inp", Input).focus()
        self.query_one("#log", RichLog).write("[green]App started. Try typing and pressing Enter.[/green]")

    def on_key(self, event) -> None:
        self.query_one("#info", Static).update(f"Key event: [bold]{event.key!r}[/bold]")
        self.query_one("#log", RichLog).write(f"key: {event.key!r}")

    def on_input_changed(self, event: Input.Changed) -> None:
        self.query_one("#log", RichLog).write(f"changed: {event.value!r}")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.query_one("#log", RichLog).write(f"[bold green]SUBMITTED: {event.value!r}[/bold green]")
        self.query_one("#info", Static).update(f"[green]Submitted: {event.value!r}[/green]")
        event.input.clear()


DebugApp().run()
