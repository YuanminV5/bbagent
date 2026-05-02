from __future__ import annotations

import asyncio
import os
import uuid

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer, Vertical
from textual.widgets import Header, Input, RichLog, Static

from .orchestrator import Orchestrator, Session

STATUS_STYLE: dict[str, tuple[str, str]] = {
    "pending": ("dim",    "○ pending"),
    "running": ("yellow", "● running"),
    "done":    ("green",  "✓ done"),
    "error":   ("red",    "✗ error"),
}


class PromptInput(Input):
    """Input subclass that removes ctrl+c=copy so the App can handle ctrl+c=quit."""

    BINDINGS = [b for b in Input.BINDINGS if "ctrl+c" not in str(getattr(b, "key", b))]


class SessionPanel(Vertical):
    DEFAULT_CSS = """
    SessionPanel {
        border: round $primary-darken-2;
        margin: 0 0 1 0;
        height: auto;
        min-height: 5;
    }
    SessionPanel .title {
        height: 1;
        padding: 0 1;
        background: $surface-darken-1;
    }
    SessionPanel RichLog {
        min-height: 3;
        max-height: 15;
        height: auto;
        padding: 0 1;
    }
    """

    def __init__(self, session: Session) -> None:
        super().__init__(id=f"panel-{session.id}")
        self._sid = session.id
        self._name = session.name

    def compose(self) -> ComposeResult:
        _, label = STATUS_STYLE["pending"]
        yield Static(f"[bold]{self._name}[/bold]  {label}", classes="title", id=f"t-{self._sid}")
        yield RichLog(id=f"l-{self._sid}", highlight=False, markup=True)

    def set_status(self, status: str) -> None:
        style, label = STATUS_STYLE.get(status, ("dim", status))
        self.query_one(f"#t-{self._sid}", Static).update(
            f"[bold]{self._name}[/bold]  [{style}]{label}[/{style}]"
        )

    def append_line(self, text: str) -> None:
        self.query_one(f"#l-{self._sid}", RichLog).write(text)


class BbagentApp(App):
    TITLE = "bbagent"
    CSS = """
    Screen { layout: vertical; }
    #sessions {
        height: 1fr;
        padding: 0 1;
        overflow-y: auto;
    }
    #hints {
        height: 1;
        padding: 0 1;
        background: $surface-darken-1;
        color: $text-muted;
    }
    PromptInput {
        height: 3;
        border-top: solid $primary-darken-2;
        background: transparent;
        border: none;
        padding: 0 1;
    }
    """
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    initial_task: str | None = None

    def __init__(self, cwd: str | None = None) -> None:
        super().__init__()
        self._cwd = cwd or os.getcwd()
        self._orchestrator = Orchestrator(cwd=self._cwd)
        self._panels: dict[str, SessionPanel] = {}
        self._running = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield ScrollableContainer(id="sessions")
        yield Static(
            "  [b]Enter[/b] submit   [b]Ctrl+C[/b] quit   [b]↑ ↓[/b] scroll",
            id="hints",
        )
        yield PromptInput(placeholder="  Type a task and press Enter...", id="prompt")

    def action_quit(self) -> None:
        self.exit()

    def on_mount(self) -> None:
        self.query_one("#prompt", PromptInput).focus()
        if self.initial_task:
            asyncio.get_event_loop().call_soon(
                lambda: asyncio.ensure_future(self._handle_task(self.initial_task))
            )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Fallback handler (method form, fires for any Input in the tree)."""
        task = event.value.strip()
        if not task or self._running:
            return
        event.input.clear()
        asyncio.ensure_future(self._handle_task(task))

    async def _handle_task(self, task: str) -> None:
        self._running = True
        container = self.query_one("#sessions", ScrollableContainer)

        for panel in list(self._panels.values()):
            await panel.remove()
        self._panels.clear()

        planning = Static(f"[dim]  Planning: {task}...[/dim]", id="planning")
        await container.mount(planning)

        try:
            subtasks = await self._orchestrator.plan_subtasks(task)
        except Exception as exc:
            try:
                await planning.remove()
            except Exception:
                pass
            self.notify(f"Planning failed: {exc}", severity="error", timeout=10)
            self._running = False
            return
        else:
            try:
                await planning.remove()
            except Exception:
                pass

        sessions = [
            Session(id=uuid.uuid4().hex[:8], name=s["name"], task=s["task"])
            for s in subtasks
        ]
        self.notify(f"Spawning {len(sessions)} session(s)", timeout=3)
        for s in sessions:
            panel = SessionPanel(s)
            self._panels[s.id] = panel
            await container.mount(panel)

        async def _on_line(sid: str, line: str) -> None:
            panel = self._panels.get(sid)
            if panel is None:
                return
            sess = next((s for s in sessions if s.id == sid), None)
            if sess:
                panel.set_status(sess.status)
            if line:
                panel.append_line(line)

        try:
            await asyncio.gather(
                *[self._orchestrator.run_session(s, _on_line) for s in sessions]
            )
        except Exception as exc:
            self.notify(f"Session error: {exc}", severity="error", timeout=10)
        finally:
            self._running = False
            self.query_one("#prompt", PromptInput).focus()
