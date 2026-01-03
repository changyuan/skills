#!/usr/bin/env python3
"""
Tool Caller - Direct tool invocation without MCP protocol.

This module provides utilities for calling MCP server tools
directly through subprocess or import, bypassing the MCP protocol.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


class ToolCaller:
    """Direct tool invocation interface."""

    def __init__(self, server_command: str, server_args: Optional[List[str]] = None):
        """
        Initialize the tool caller.

        Args:
            server_command: Command to start the server
            server_args: Arguments for the server command
        """
        self.server_command = server_command
        self.server_args = server_args or []
        self._process: Optional[subprocess.Popen] = None

    def start(self) -> None:
        """Start the server process."""
        self._process = subprocess.Popen(
            [self.server_command] + self.server_args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
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

    def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call a tool on the server.

        Args:
            tool_name: Name of the tool to call
            args: Arguments for the tool

        Returns:
            Tool response as dictionary
        """
        if not self._process:
            raise RuntimeError("Server not running. Call start() first.")

        request = json.dumps({"tool": tool_name, "args": args}) + "\n"
        self._process.stdin.write(request)
        self._process.stdin.flush()

        response_line = self._process.stdout.readline()
        return json.loads(response_line)

    def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools from the server."""
        if not self._process:
            raise RuntimeError("Server not running. Call start() first.")

        request = json.dumps({"action": "list_tools"}) + "\n"
        self._process.stdin.write(request)
        self._process.stdin.flush()

        response_line = self._process.stdout.readline()
        return json.loads(response_line)


class DirectToolCaller:
    """Call tools via direct module import."""

    def __init__(self, module_path: str):
        """
        Initialize with module path.

        Args:
            module_path: Dot-separated path to server module
        """
        self.module_path = module_path
        self._module = None

    def _load_module(self):
        """Load the server module."""
        import importlib

        if not self._module:
            self._module = importlib.import_module(self.module_path)
        return self._module

    def get_tools(self) -> List[Dict[str, Any]]:
        """Get available tools."""
        module = self._load_module()

        if hasattr(module, "list_tools"):
            return module.list_tools()
        if hasattr(module, "get_tools"):
            return module.get_tools()
        if hasattr(module, "tools"):
            return module.tools

        return []

    def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """Call a tool directly."""
        module = self._load_module()

        # Try various calling patterns
        if hasattr(module, tool_name):
            func = getattr(module, tool_name)
            if callable(func):
                return func(**args)

        if hasattr(module, "call_tool"):
            return module.call_tool(tool_name, args)

        raise ValueError(f"Tool {tool_name} not found in {self.module_path}")


def parse_tool_input(input_str: str) -> Dict[str, Any]:
    """Parse JSON or key=value input into a dictionary."""
    input_str = input_str.strip()

    if not input_str:
        return {}

    # Try JSON first
    try:
        return json.loads(input_str)
    except json.JSONDecodeError:
        pass

    # Fall back to key=value parsing
    result = {}
    for pair in input_str.split(","):
        if "=" in pair:
            key, value = pair.split("=", 1)
            result[key.strip()] = value.strip()

    return result


def format_tool_result(result: Any) -> str:
    """Format tool result for display."""
    if isinstance(result, (dict, list)):
        return json.dumps(result, indent=2)
    return str(result)


def main():
    parser = argparse.ArgumentParser(
        description="Call tools directly without MCP protocol",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # List tools command
    list_parser = subparsers.add_parser("list", help="List available tools")
    list_parser.add_argument("--module", help="Module path for direct import")

    # Call tool command
    call_parser = subparsers.add_parser("call", help="Call a tool")
    call_parser.add_argument("tool", help="Tool name")
    call_parser.add_argument("input", nargs="?", default="{}", help="Tool input (JSON or key=value)")
    call_parser.add_argument("--module", help="Module path for direct import")

    # Server mode
    parser.add_argument("--command", help="Server command to run")
    parser.add_argument("--args", nargs="+", help="Server arguments")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")

    args = parser.parse_args()

    if args.command:
        # Server mode
        caller = ToolCaller(args.command, args.args)

        if args.interactive:
            # Interactive mode
            print(f"Starting server: {args.command} {' '.join(args.args or [])}")
            caller.start()
            print("Server started. Type 'quit' to exit.")
            print("Usage: <tool_name> <json_input>")

            try:
                while True:
                    line = input("> ").strip()
                    if line.lower() in ("quit", "exit", "q"):
                        break
                    if not line:
                        continue

                    parts = line.split(None, 1)
                    if len(parts) == 1:
                        tool_name = parts[0]
                        tool_args = {}
                    else:
                        tool_name, input_str = parts
                        tool_args = parse_tool_input(input_str)

                    try:
                        result = caller.call_tool(tool_name, tool_args)
                        print(format_tool_result(result))
                    except Exception as e:
                        print(f"Error: {e}")
            finally:
                caller.stop()
        else:
            print("Server mode requires --interactive flag")
    elif args.command is None and args.module:
        # Direct import mode
        caller = DirectToolCaller(args.module)

        if args.command == "list":
            tools = caller.get_tools()
            print(f"Available tools ({len(tools)}):")
            for tool in tools:
                print(f"  - {tool.get('name', 'unknown')}: {tool.get('description', 'No description')[:60]}")

        elif args.command == "call":
            tool_args = parse_tool_input(args.input)
            try:
                result = caller.call_tool(args.tool, tool_args)
                print(format_tool_result(result))
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
