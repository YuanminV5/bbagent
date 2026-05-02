import asyncio
import json
from claude_code_sdk import query, ClaudeCodeOptions
from claude_code_sdk.types import AssistantMessage, ResultMessage, TextBlock, ToolUseBlock


def _fmt(inp: dict) -> str:
    parts = []
    for k, v in inp.items():
        val = json.dumps(v) if not isinstance(v, str) else repr(v)
        if len(val) > 80:
            val = val[:77] + "..."
        parts.append(f"{k}={val}")
    return ", ".join(parts)


async def _run(task: str, cwd: str = ".") -> str:
    options = ClaudeCodeOptions(
        permission_mode="bypassPermissions",
        max_turns=30,
        cwd=cwd,
    )

    result_text = ""
    async for message in query(prompt=task, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock) and block.text:
                    print(block.text, end="", flush=True)
                elif isinstance(block, ToolUseBlock):
                    print(f"\n[tool] {block.name}({_fmt(block.input)})", flush=True)
        elif isinstance(message, ResultMessage):
            result_text = message.result or ""
            if message.is_error:
                print("\n[error] task ended with an error", flush=True)

    return result_text


def run(task: str, cwd: str = ".") -> str:
    return asyncio.run(_run(task, cwd))
