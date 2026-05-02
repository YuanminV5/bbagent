# bbagent

An autonomous multi-session agent: Claude Code SDK handles execution and auth;
a Python orchestrator breaks tasks into parallel subtasks; a Textual TUI displays
all sessions live. No API key required — uses the user's existing Claude Code login.

## Project map

- `agent.py` — CLI entry point
- `agent/core.py` — single-session runner (simple use / testing)
- `agent/orchestrator.py` — `Session` dataclass + `Orchestrator` (plan + run sessions)
- `agent/tui.py` — Textual app (`BbagentApp`, `SessionPanel`, `PromptInput`)
- `design.md` — architecture reference for collaborators

## Keeping design.md up to date

Update `design.md` whenever a change affects any of the following:

- The architecture diagram or data flow (new components, changed call paths)
- A component's public interface (renamed/added/removed methods or classes)
- A key design decision being reversed or superseded
- New dependencies added to `pyproject.toml`
- Auth or setup steps changing

Do **not** update `design.md` for bug fixes, refactors that preserve behaviour,
or CSS/style-only changes.

When updating, edit only the affected section(s) — do not rewrite the whole file.
