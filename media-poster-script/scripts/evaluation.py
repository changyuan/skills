#!/usr/bin/env python3
"""
Media Poster Script Evaluation Harness

Evaluates MCP servers using standalone Python scripts without MCP protocol.
Replaces MCP ClientSession with direct subprocess calls and Claude API.
"""

import argparse
import asyncio
import json
import re
import sys
import time
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional

from anthropic import Anthropic


EVALUATION_PROMPT = """You are an AI assistant with access to tools.

When given a task, you MUST:
1. Use the available tools to complete the task
2. Provide summary of each step in your approach, wrapped in <summary> tags
3. Provide your final response, wrapped in <response> tags

Summary Requirements:
- In your <summary> tags, you must explain:
  - The steps you took to complete the task
  - Which tools you used, in what order, and why
  - The inputs you provided to each tool
  - The outputs you received from each tool
  - A summary for how you arrived at the response

Response Requirements:
- Your response should be concise and directly address what was asked
- Always wrap your final response in <response> tags
- If you cannot solve the task return <response>NOT_FOUND</response>
- For numeric responses, provide just the number
- For IDs, provide just the ID
- For names or text, provide the exact text requested
- Your response should go last"""


def parse_evaluation_file(file_path: Path) -> List[Dict[str, Any]]:
    """Parse XML evaluation file with qa_pair elements."""
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        evaluations = []

        for qa_pair in root.findall(".//qa_pair"):
            question_elem = qa_pair.find("question")
            answer_elem = qa_pair.find("answer")

            if question_elem is not None and answer_elem is not None:
                evaluations.append({
                    "question": (question_elem.text or "").strip(),
                    "answer": (answer_elem.text or "").strip(),
                })

        return evaluations
    except Exception as e:
        print(f"Error parsing evaluation file {file_path}: {e}")
        return []


def extract_xml_content(text: str, tag: str) -> Optional[str]:
    """Extract content from XML tags."""
    pattern = rf"<{tag}>(.*?)</{tag}>"
    matches = re.findall(pattern, text, re.DOTALL)
    return matches[-1].strip() if matches else None


class ScriptBasedToolCaller:
    """Call tools through script execution instead of MCP protocol."""

    def __init__(
        self,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize the script-based tool caller.

        Args:
            command: Executable command to run the server
            args: Command arguments
            env: Environment variables
        """
        self.command = command
        self.args = args or []
        self.env = env or {}
        self._process = None

    def start(self) -> None:
        """Start the server process."""
        import os

        env = os.environ.copy()
        env.update(self.env)

        self._process = subprocess.Popen(
            [self.command] + self.args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

    def stop(self) -> None:
        """Stop the server process."""
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
        self._process = None

    def list_tools(self) -> List[Dict[str, Any]]:
        """Get available tools from the server."""
        if not self._process:
            raise RuntimeError("Server not running")

        request = json.dumps({"action": "list_tools"}) + "\n"
        self._process.stdin.write(request)
        self._process.stdin.flush()

        response_line = self._process.stdout.readline()
        return json.loads(response_line)

    def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """Call a tool on the server."""
        if not self._process:
            raise RuntimeError("Server not running")

        request = json.dumps({"tool": tool_name, "args": args}) + "\n"
        self._process.stdin.write(request)
        self._process.stdin.flush()

        response_line = self._process.stdout.readline()
        result = json.loads(response_line)

        # Handle error responses
        if isinstance(result, dict) and "error" in result:
            raise RuntimeError(result["error"])

        return result


class DirectToolCaller:
    """Call tools through direct module imports."""

    def __init__(self, module_path: str):
        self.module_path = module_path
        self._module = None

    def _load_module(self):
        """Load the server module."""
        import importlib

        if not self._module:
            self._module = importlib.import_module(self.module_path)
        return self._module

    def list_tools(self) -> List[Dict[str, Any]]:
        """Get available tools from the module."""
        module = self._load_module()

        if hasattr(module, "list_tools"):
            return module.list_tools()
        if hasattr(module, "get_tools"):
            return module.get_tools()
        if hasattr(module, "tools"):
            return module.tools

        return []

    def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """Call a tool directly on the module."""
        module = self._load_module()

        # Try module-level function
        if hasattr(module, tool_name):
            func = getattr(module, tool_name)
            if callable(func):
                return func(**args)

        # Try call_tool function
        if hasattr(module, "call_tool"):
            return module.call_tool(tool_name, args)

        raise ValueError(f"Tool {tool_name} not found in {self.module_path}")


async def agent_loop(
    client: Anthropic,
    model: str,
    question: str,
    tools: List[Dict[str, Any]],
    tool_caller: Any,
) -> tuple[str, Dict[str, Any]]:
    """Run the agent loop with script-based tool calling."""
    messages = [{"role": "user", "content": question}]

    response = await asyncio.to_thread(
        client.messages.create,
        model=model,
        max_tokens=4096,
        system=EVALUATION_PROMPT,
        messages=messages,
        tools=tools,
    )

    messages.append({"role": "assistant", "content": response.content})

    tool_metrics = {}

    while response.stop_reason == "tool_use":
        tool_use = next(block for block in response.content if block.type == "tool_use")
        tool_name = tool_use.name
        tool_input = tool_use.input

        tool_start_ts = time.time()
        try:
            tool_result = tool_caller.call_tool(tool_name, tool_input)
            tool_response = json.dumps(tool_result) if isinstance(tool_result, (dict, list)) else str(tool_result)
        except Exception as e:
            tool_response = f"Error executing tool {tool_name}: {str(e)}\n"
            tool_response += traceback.format_exc()
        tool_duration = time.time() - tool_start_ts

        if tool_name not in tool_metrics:
            tool_metrics[tool_name] = {"count": 0, "durations": []}
        tool_metrics[tool_name]["count"] += 1
        tool_metrics[tool_name]["durations"].append(tool_duration)

        messages.append({
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": tool_response,
            }]
        })

        response = await asyncio.to_thread(
            client.messages.create,
            model=model,
            max_tokens=4096,
            system=EVALUATION_PROMPT,
            messages=messages,
            tools=tools,
        )
        messages.append({"role": "assistant", "content": response.content})

    response_text = next(
        (block.text for block in response.content if hasattr(block, "text")),
        None,
    )
    return response_text, tool_metrics


async def evaluate_single_task(
    client: Anthropic,
    model: str,
    qa_pair: Dict[str, Any],
    tools: List[Dict[str, Any]],
    tool_caller: Any,
    task_index: int,
) -> Dict[str, Any]:
    """Evaluate a single QA pair."""
    start_time = time.time()

    print(f"Task {task_index + 1}: {qa_pair['question'][:60]}...")
    response, tool_metrics = await agent_loop(client, model, qa_pair["question"], tools, tool_caller)

    response_value = extract_xml_content(response, "response")
    summary = extract_xml_content(response, "summary")

    duration_seconds = time.time() - start_time

    return {
        "question": qa_pair["question"],
        "expected": qa_pair["answer"],
        "actual": response_value,
        "score": int(response_value == qa_pair["answer"]) if response_value else 0,
        "total_duration": duration_seconds,
        "tool_calls": tool_metrics,
        "num_tool_calls": sum(len(metrics["durations"]) for metrics in tool_metrics.values()),
        "summary": summary,
    }


REPORT_HEADER = """
# Evaluation Report

## Summary

- **Accuracy**: {correct}/{total} ({accuracy:.1f}%)
- **Average Task Duration**: {average_duration_s:.2f}s
- **Average Tool Calls per Task**: {average_tool_calls:.2f}
- **Total Tool Calls**: {total_tool_calls}

---
"""

TASK_TEMPLATE = """
### Task {task_num}

**Question**: {question}
**Ground Truth Answer**: `{expected_answer}`
**Actual Answer**: `{actual_answer}`
**Correct**: {correct_indicator}
**Duration**: {total_duration:.2f}s
**Tool Calls**: {tool_calls}

**Summary**
{summary}

---
"""


async def run_evaluation(
    eval_path: Path,
    tool_caller: Any,
    model: str = "claude-3-7-sonnet-20250219",
) -> str:
    """Run evaluation with script-based tool calling."""
    print("Starting Evaluation")

    client = Anthropic()

    tools = tool_caller.list_tools()
    print(f"Loaded {len(tools)} tools")

    qa_pairs = parse_evaluation_file(eval_path)
    print(f"Loaded {len(qa_pairs)} evaluation tasks")

    results = []
    for i, qa_pair in enumerate(qa_pairs):
        print(f"Processing task {i + 1}/{len(qa_pairs)}")
        result = await evaluate_single_task(client, model, qa_pair, tools, tool_caller, i)
        results.append(result)

    correct = sum(r["score"] for r in results)
    accuracy = (correct / len(results)) * 100 if results else 0
    average_duration_s = sum(r["total_duration"] for r in results) / len(results) if results else 0
    average_tool_calls = sum(r["num_tool_calls"] for r in results) / len(results) if results else 0
    total_tool_calls = sum(r["num_tool_calls"] for r in results)

    report = REPORT_HEADER.format(
        correct=correct,
        total=len(results),
        accuracy=accuracy,
        average_duration_s=average_duration_s,
        average_tool_calls=average_tool_calls,
        total_tool_calls=total_tool_calls,
    )

    report += "".join([
        TASK_TEMPLATE.format(
            task_num=i + 1,
            question=qa_pair["question"],
            expected_answer=qa_pair["answer"],
            actual_answer=result["actual"] or "N/A",
            correct_indicator="PASS" if result["score"] else "FAIL",
            total_duration=result["total_duration"],
            tool_calls=json.dumps(result["tool_calls"], indent=2),
            summary=result["summary"] or "N/A",
        )
        for i, (qa_pair, result) in enumerate(zip(qa_pairs, results))
    ])

    return report


def parse_headers(header_list: List[str]) -> Dict[str, str]:
    """Parse header strings in format 'Key: Value' into a dictionary."""
    headers = {}
    if not header_list:
        return headers

    for header in header_list:
        if ":" in header:
            key, value = header.split(":", 1)
            headers[key.strip()] = value.strip()
    return headers


def parse_env_vars(env_list: List[str]) -> Dict[str, str]:
    """Parse environment variable strings in format 'KEY=VALUE' into a dictionary."""
    env = {}
    if not env_list:
        return env

    for env_var in env_list:
        if "=" in env_var:
            key, value = env_var.split("=", 1)
            env[key.strip()] = value.strip()
    return env


async def main():
    parser = argparse.ArgumentParser(
        description="Evaluate MCP servers using script-based tool calling",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Evaluate with stdio transport
  python evaluation.py -c python -a media_poster_server.py eval.xml

  # Evaluate with environment variables
  python evaluation.py -c python -a server.py -e "API_KEY=key" eval.xml

  # Evaluate using direct module import
  python evaluation.py --module media_poster.server eval.xml
        """,
    )

    parser.add_argument("eval_file", type=Path, help="Path to evaluation XML file")
    parser.add_argument("-m", "--model", default="claude-3-7-sonnet-20250219", help="Claude model to use")

    stdio_group = parser.add_argument_group("stdio options")
    stdio_group.add_argument("-c", "--command", help="Command to run server")
    stdio_group.add_argument("-a", "--args", nargs="+", help="Arguments for the command")
    stdio_group.add_argument("-e", "--env", nargs="+", help="Environment variables in KEY=VALUE format")

    direct_group = parser.add_argument_group("direct import options")
    direct_group.add_argument("--module", help="Module path for direct import (e.g., media_poster.server)")

    parser.add_argument("-o", "--output", type=Path, help="Output file for report")

    args = parser.parse_args()

    if not args.eval_file.exists():
        print(f"Error: Evaluation file not found: {args.eval_file}")
        sys.exit(1)

    # Create appropriate tool caller
    if args.module:
        tool_caller = DirectToolCaller(args.module)
    elif args.command:
        env_vars = parse_env_vars(args.env) if args.env else {}
        tool_caller = ScriptBasedToolCaller(command=args.command, args=args.args, env=env_vars)
    else:
        print("Error: Either --command or --module must be specified")
        sys.exit(1)

    print(f"Starting evaluation with {args.eval_file}")

    try:
        if hasattr(tool_caller, "start"):
            tool_caller.start()
            print("Server started")

        report = await run_evaluation(args.eval_file, tool_caller, args.model)

        if args.output:
            args.output.write_text(report)
            print(f"Report saved to {args.output}")
        else:
            print("\n" + report)

    finally:
        if hasattr(tool_caller, "stop"):
            tool_caller.stop()
            print("Server stopped")


if __name__ == "__main__":
    asyncio.run(main())
