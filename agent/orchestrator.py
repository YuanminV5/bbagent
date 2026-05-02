import asyncio
import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Callable, Awaitable

from claude_code_sdk import query, ClaudeCodeOptions
from claude_code_sdk.types import AssistantMessage, ResultMessage, TextBlock, ToolUseBlock


@dataclass
class Session:
    id: str
    name: str
    task: str
    status: str = "pending"   # pending | running | done | error
    lines: list[str] = field(default_factory=list)
    result: str = ""


OnLine = Callable[[str, str], Awaitable[None]]  # (session_id, line) -> None


class Orchestrator:
    def __init__(self, cwd: str = "."):
        self.cwd = cwd

    async def plan_subtasks(self, task: str) -> list[dict]:
        prompt = (
            "Break this task into parallel subtasks that can run independently and concurrently. "
            "Reply with ONLY a JSON array — no explanation, no markdown fences: "
            '[{"name": "<short label>", "task": "<full subtask description>"}]. '
            "If the task cannot be parallelised, return a single-element array. "
            f"Task: {task}"
        )
        text_buf = ""
        async for message in query(
            prompt=prompt,
            options=ClaudeCodeOptions(max_turns=1, allowed_tools=[]),
        ):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        text_buf += block.text
            elif isinstance(message, ResultMessage) and message.result:
                text_buf = text_buf or message.result

        # Strip markdown fences if Claude wrapped the JSON anyway
        text_buf = re.sub(r"```[a-z]*\n?", "", text_buf).strip()

        try:
            subtasks = json.loads(text_buf)
            if isinstance(subtasks, list) and subtasks:
                return subtasks
        except (json.JSONDecodeError, ValueError):
            pass

        return [{"name": "main", "task": task}]

    async def run_session(self, session: Session, on_line: OnLine) -> None:
        session.status = "running"
        await on_line(session.id, "")

        try:
            async for message in query(
                prompt=session.task,
                options=ClaudeCodeOptions(
                    permission_mode="bypassPermissions",
                    max_turns=30,
                    cwd=self.cwd,
                ),
            ):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock) and block.text:
                            for line in block.text.splitlines():
                                session.lines.append(line)
                                await on_line(session.id, line)
                        elif isinstance(block, ToolUseBlock):
                            # Compact tool display: show first arg value only
                            first_val = next(iter(block.input.values()), "") if block.input else ""
                            if isinstance(first_val, str) and len(first_val) > 60:
                                first_val = first_val[:57] + "..."
                            line = f"[tool] {block.name}({first_val!r})"
                            session.lines.append(line)
                            await on_line(session.id, line)
                elif isinstance(message, ResultMessage):
                    session.result = message.result or ""
                    session.status = "error" if message.is_error else "done"
                    await on_line(session.id, "")
        except Exception as exc:
            session.status = "error"
            session.result = str(exc)
            await on_line(session.id, f"[error] {exc}")

    async def run(self, task: str, on_line: OnLine) -> list[Session]:
        subtasks = await self.plan_subtasks(task)
        sessions = [
            Session(id=uuid.uuid4().hex[:8], name=s["name"], task=s["task"])
            for s in subtasks
        ]
        await asyncio.gather(*[self.run_session(s, on_line) for s in sessions])
        return sessions
