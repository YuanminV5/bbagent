# bbagent — Design Document

## Overview

bbagent is an autonomous agent that accepts a natural-language task, breaks it into
parallel subtasks using Claude, and executes each subtask concurrently in its own
Claude Code session. A Textual-based TUI displays all sessions live in the terminal.

**No API key required.** Authentication is handled by the user's existing Claude Code
login (`claude auth login`).

---

## UI

```
┌─ bbagent ───────────────────────────────── 2 sessions ─┐
│                                                         │
│ ┌─ backend  [● running] ──────────────────────────────┐ │
│ │ [tool] Bash('mkdir backend && cd backend')          │ │
│ │ [tool] Write('main.py')                             │ │
│ │ Creating FastAPI project...                         │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ ┌─ tests    [✓ done] ─────────────────────────────────┐ │
│ │ All 12 tests passing.                               │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│   Enter submit   Ctrl+C quit   ↑ ↓ scroll               │
│ > Type a task and press Enter...                        │
└─────────────────────────────────────────────────────────┘
```

---

## Architecture

```
agent.py  (CLI entry point)
    └── BbagentApp.run()          Textual TUI, blocks until quit
              │
              │  user submits task (Enter)
              ▼
        BbagentApp._handle_task(task)
              │
              ├── 1. Orchestrator.plan_subtasks(task)
              │         └── claude_code_sdk.query()
              │               max_turns=1, allowed_tools=[]
              │               → parses JSON array of subtasks
              │               → fallback: [{name:"main", task:task}]
              │
              └── 2. asyncio.gather(
                        Orchestrator.run_session(session_A, on_line),
                        Orchestrator.run_session(session_B, on_line),
                        ...
                    )
                          └── each: claude_code_sdk.query(session.task)
                                → streams TextBlock / ToolUseBlock
                                → calls on_line(session_id, line)
                                          │
                                          ▼
                                  SessionPanel.append_line(line)
                                  (live update in TUI)
```

---

## File Structure

```
bbagent/
├── agent.py                 CLI entry point
├── agent/
│   ├── __init__.py
│   ├── core.py              Single-session runner (simple use / testing)
│   ├── orchestrator.py      Session dataclass + Orchestrator class
│   └── tui.py               Textual app — BbagentApp + SessionPanel
├── .env.template            Documents required env vars
├── .python-version          Pins Python 3.12
└── pyproject.toml           Dependencies: claude-code-sdk, textual
```

---

## Components

### `agent.py`

Entry point. Instantiates `BbagentApp`, optionally sets `initial_task` from the
CLI argument, and calls `app.run()`.

```
uv run python agent.py                          # interactive mode
uv run python agent.py "build a REST API"       # one-shot, auto-submits on launch
```

---

### `agent/orchestrator.py`

#### `Session`
Dataclass tracking one sub-session's lifecycle.

| Field | Type | Description |
|---|---|---|
| `id` | `str` | 8-char hex UUID, used as widget IDs in TUI |
| `name` | `str` | Short human label, e.g. `"backend"` |
| `task` | `str` | Full subtask prompt sent to Claude |
| `status` | `str` | `pending` → `running` → `done` / `error` |
| `lines` | `list[str]` | Accumulated output lines |
| `result` | `str` | Final `ResultMessage.result` text |

#### `Orchestrator`

**`plan_subtasks(task) → list[dict]`**

Calls `claude_code_sdk.query()` with `max_turns=1, allowed_tools=[]` — one text
response, no tool use. Prompts Claude to return a JSON array:
```json
[{"name": "backend", "task": "Create a FastAPI app..."}, ...]
```
Strips any accidental markdown fences, parses JSON. Falls back to
`[{"name": "main", "task": task}]` if parsing fails — so single tasks always work.

**`run_session(session, on_line)`**

Runs one `query()` session with `permission_mode="bypassPermissions"` and
`max_turns=30`. For each message received:
- `TextBlock` → splits into lines, calls `on_line(session.id, line)`
- `ToolUseBlock` → formats as `[tool] Name('first arg...')`, calls `on_line`
- `ResultMessage` → sets `session.status` to `done` or `error`

**`run(task, on_line) → list[Session]`**

Convenience wrapper: calls `plan_subtasks`, creates `Session` objects, runs all
via `asyncio.gather` (true concurrency in the same event loop).

---

### `agent/tui.py`

#### `PromptInput(Input)`

Subclass of Textual's `Input` with the built-in `ctrl+c → copy` binding removed.
Without this, the `Input` widget captures Ctrl+C before the App can use it to quit.

#### `SessionPanel(Vertical)`

Composite widget for one sub-session. Contains:
- `Static` title bar — shows session name and a coloured status badge
- `RichLog` — append-only scrollable log, supports Rich markup

| Status | Colour | Badge |
|---|---|---|
| pending | dim | ○ pending |
| running | yellow | ● running |
| done | green | ✓ done |
| error | red | ✗ error |

#### `BbagentApp(App)`

Main Textual application.

**Layout (top → bottom):**
```
Header          (Textual built-in, shows app title)
ScrollableContainer #sessions    (height: 1fr — all panels mount here)
Static #hints   (keyboard shortcuts bar, height: 1)
PromptInput     (task input, height: 3)
```

**Task lifecycle in `_handle_task(task)`:**
1. Removes previous session panels from `#sessions`
2. Mounts a "Planning…" placeholder
3. Awaits `Orchestrator.plan_subtasks(task)`
4. Replaces placeholder with one `SessionPanel` per planned subtask
5. Runs all sessions concurrently via `asyncio.gather`; the `_on_line` callback
   updates each panel live as output arrives
6. Refocuses the input when all sessions complete

**Concurrency model:** `_handle_task` is scheduled via `asyncio.ensure_future`,
so it runs in Textual's own asyncio event loop without blocking the UI. All
`claude_code_sdk.query()` calls are also async and share the same loop.

---

### `agent/core.py`

Single-session runner, independent of the TUI. Useful for scripting or testing
without the full interface.

```python
from agent.core import run
result = run("write hello.py and run it")
```

Streams `[tool]` lines to stdout. Returns the final `ResultMessage.result` string.

---

## Authentication

bbagent uses `claude_code_sdk`, which runs the `claude` CLI as a subprocess.
Authentication is entirely handled by Claude Code — no API key is needed in the app.

**Requirement:** `claude` CLI must be installed and logged in.

```bash
# verify
claude --version
claude auth login    # only needed once
```

---

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| `claude-code-sdk` | ≥ 0.0.25 | Runs Claude Code sessions; handles auth |
| `textual` | ≥ 8.2.5 | Terminal UI framework |

Python ≥ 3.11 required (`asyncio.TaskGroup`, `match` statements). Pinned to 3.12
via `.python-version`.

---

## Setup

```bash
# 1. install uv  (skip if already installed)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 2. clone and install
git clone <repo>
cd bbagent
uv sync

# 3. log in to Claude Code (one-time)
claude auth login

# 4. run
uv run python agent.py
```

Deleting `.venv` is safe — `uv run` recreates it from `uv.lock` automatically.

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| `claude_code_sdk` over `anthropic` SDK directly | No API key needed; reuses the user's Claude Code login |
| Python orchestrator plans subtasks (not Claude-as-orchestrator) | Predictable; no risk of Claude not calling the right tool |
| `asyncio.gather` for parallelism | All sessions share Textual's event loop — no threads, no race conditions |
| `plan_subtasks` with `max_turns=1, allowed_tools=[]` | Forces a single text response; avoids Claude running tools during planning |
| Fallback to single session if planning fails | Simple tasks (or JSON parse failures) always work |
| `PromptInput` subclass strips `ctrl+c=copy` | Textual's `Input` built-in binding intercepts Ctrl+C before the App sees it |
