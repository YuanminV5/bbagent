# bbagent

An autonomous agent where Claude (Anthropic SDK Tool Runner) is the brain and tmux is the execution environment. Tools are declared with `@beta_tool` decorators; the SDK's `tool_runner()` drives the agentic loop automatically — no manual message management required.

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (package manager)
- tmux (system dependency)

## Setup

### 1. Install uv

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. Install tmux

```bash
# macOS
brew install tmux

# Linux
sudo apt install tmux        # Debian / Ubuntu
sudo dnf install tmux        # Fedora
```

> **Windows:** tmux does not run natively on Windows. Use WSL2 (Ubuntu) and install tmux inside the WSL environment, then run the agent from within WSL.

### 3. Install Python dependencies

```bash
uv sync
```

Dependencies installed: `anthropic` (includes Tool Runner), `libtmux`, `python-dotenv`.

### 4. Set your Anthropic API key

Create a `.env` file in the project root:
```
ANTHROPIC_API_KEY=sk-ant-...
```

Or export it in your shell:
```bash
# macOS / Linux
export ANTHROPIC_API_KEY=sk-ant-...

# Windows (PowerShell)
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

## Usage

```bash
uv run python agent.py "write a Python file that prints fibonacci numbers and run it"
```

## How It Works

Tools are Python functions decorated with `@beta_tool`. The SDK generates JSON schemas automatically from type annotations and docstrings, then drives the full Claude ↔ tool loop via `client.beta.messages.tool_runner()`.

```python
from anthropic import beta_tool

@beta_tool
def run_command(window: str, command: str, timeout: int = 30) -> str:
    """Run a shell command in a tmux window and return its output."""
    ...
```

## Distribution

### Windows — standalone executable

```bash
uv run pyinstaller --onefile agent.py --name bbagent
# output: dist/bbagent.exe
```

### macOS — Homebrew

```bash
brew install <tap>/bbagent
```
