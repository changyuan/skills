---
name: media-poster-script
description: Script-based evaluation harness for media-poster MCP server. Use when you need to evaluate or test MCP servers using standalone Python scripts instead of MCP protocol connections. Provides tool calling, response parsing, and automated testing without requiring MCP client sessions.
---

# Media Poster Script - MCP Server Evaluation Harness

This skill provides script-based tools for evaluating media-poster MCP servers without using MCP protocol connections. All functionality is achieved through direct Python script execution.

## Overview

Evaluate media-poster MCP servers using standalone Python scripts that:
- Execute server processes directly via subprocess
- Call server tools through Python imports or direct invocation
- Parse JSON responses and verify expected outputs
- Run automated evaluation test suites

## When to Use This Skill

Use when:
- Testing MCP server implementations without MCP client setup
- Running automated evaluations in CI/CD pipelines
- Needing deterministic, script-controlled test execution
- Avoiding MCP protocol overhead for simple tool testing

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                 Evaluation Script                        │
│  (evaluation.py - orchestrates all tests)              │
└────────────────┬────────────────────────────────────────┘
                 │
                 │ subprocess / direct import
                 ▼
┌─────────────────────────────────────────────────────────┐
│              media-poster MCP Server                     │
│  (running as standalone process)                        │
└─────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# Run evaluation on media-poster server
python scripts/evaluation.py --command "python" --args "media_poster_server.py" eval.xml

# Or with direct tool calling
python scripts/tool_caller.py --tool list_movies --input "{}"
```

## Scripts

### evaluation.py

Main evaluation harness that runs test questions against the media-poster server.

```bash
# Basic usage with stdio transport (recommended for local servers)
python scripts/evaluation.py \
  --command python \
  --args media_poster_server.py \
  --eval eval.xml

# With environment variables
python scripts/evaluation.py \
  --command python \
  --args media_poster_server.py \
  --env "API_KEY=your_key" \
  --eval eval.xml
```

**Arguments:**
- `--command`: Executable command to run server
- `--args`: Arguments passed to command
- `--env`: Environment variables (KEY=VALUE format)
- `--eval`: Path to evaluation XML file

**Output:**
- Console summary of pass/fail results
- Detailed report saved to `evaluation_report.md`

### tool_caller.py

Direct tool invocation without MCP protocol.

```bash
# Call a specific tool
python scripts/tool_caller.py --tool get_movie --input '{"id": "123"}'

# List available tools
python scripts/tool_caller.py --list-tools
```

### server_runner.py

Utility for managing server process lifecycle.

```python
from server_runner import ServerRunner

runner = ServerRunner(command="python", args=["server.py"])
with runner.run() as process:
    # Send input, get output
    result = runner.send_tool_call("get_movie", {"id": "123"})
```

## Evaluation File Format

Create XML files with test questions and expected answers:

```xml
<evaluation>
  <qa_pair>
    <question>What is the title of movie ID 123?</question>
    <answer>Inception</answer>
  </qa_pair>
  <qa_pair>
    <question>List all action movies from 2020</question>
    <answer>3</answer>
  </qa_pair>
</evaluation>
```

**Requirements:**
- Independent: Each question stands alone
- Read-only: No destructive operations required
- Complex: Requires multiple tool calls
- Realistic: Based on actual use cases
- Verifiable: Single, clear answer

## Reference

### Scripts API

**server_runner.py:**
```python
class ServerRunner:
    def __init__(self, command: str, args: list[str], env: dict[str, str] = None)
    def run() -> ContextManager[subprocess.Popen]
    def send_tool_call(tool_name: str, args: dict) -> dict
    def get_tools() -> list[dict]
```

**tool_caller.py:**
```python
def call_tool(tool_name: str, args: dict, server_process: Popen) -> dict
def list_tools(server_process: Popen) -> list[dict]
def parse_tool_result(output: str) -> dict
```

### MCP Pattern Reference

For tool design and evaluation guidelines, see:
- [MCP Best Practices](./reference/mcp_best_practices.md) - Tool naming, response formats
- [Evaluation Guide](./reference/evaluation.md) - Question creation, answer verification

## Directory Structure

```
media-poster-script/
├── SKILL.md                    # This file
├── scripts/
│   ├── evaluation.py           # Main evaluation harness
│   ├── tool_caller.py          # Direct tool invocation
│   ├── server_runner.py        # Server process management
│   ├── connections.py          # MCP-compatible connection interface
│   └── requirements.txt        # Python dependencies
├── reference/
│   ├── mcp_best_practices.md   # MCP tool design guidelines
│   └── evaluation.md           # Evaluation creation guide
└── assets/
    └── example_evaluation.xml  # Sample evaluation file
```

## Dependencies

Install required packages:

```bash
pip install -r scripts/requirements.txt
```

Key dependencies:
- `anthropic` - Claude API client
- `python-dotenv` - Environment variable loading

## Limitations

- Requires server to be callable via command line or import
- Tool schemas must be known in advance for tool_caller.py
- Server must output JSON-serializable responses

## Next Steps

1. Place your media-poster MCP server code in the same directory
2. Create evaluation XML file with test questions
3. Run `python scripts/evaluation.py` to start testing
