#!/usr/bin/env python3
"""
Connection Handlers - MCP-compatible interface without MCP protocol.

This module provides connection classes that mimic MCP ClientSession
but use direct subprocess calls or module imports instead.
"""

import asyncio
import json
import subprocess
from abc import ABC, abstractmethod
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Dict, List, Optional


class ConnectionBase(ABC):
    """Base class for connection handlers."""

    def __init__(self):
        self.session = None
        self._stack = None

    @abstractmethod
    def list_tools(self) -> List[Dict[str, Any]]:
        """Retrieve available tools."""

    @abstractmethod
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool with arguments."""

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        pass


class StdioConnection(ConnectionBase):
    """Connection using standard input/output (no MCP protocol)."""

    def __init__(
        self,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        working_dir: Optional[Path] = None,
    ):
        super().__init__()
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.working_dir = working_dir
        self._process: Optional[subprocess.Popen] = None

    def _ensure_running(self):
        """Ensure the server process is running."""
        if self._process is None or self._process.poll() is not None:
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
                cwd=self.working_dir,
            )

    def list_tools(self) -> List[Dict[str, Any]]:
        """Retrieve available tools from the server."""
        self._ensure_running()

        request = json.dumps({"action": "list_tools"}) + "\n"
        self._process.stdin.write(request)
        self._process.stdin.flush()

        response_line = self._process.stdout.readline()
        return json.loads(response_line)

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on the server."""
        self._ensure_running()

        request = json.dumps({"tool": tool_name, "args": arguments}) + "\n"
        self._process.stdin.write(request)
        self._process.stdin.flush()

        response_line = self._process.stdout.readline()
        result = json.loads(response_line)

        if isinstance(result, dict) and "error" in result:
            raise RuntimeError(result["error"])

        return result

    def stop(self):
        """Stop the server process."""
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
        self._process = None


class DirectConnection(ConnectionBase):
    """Connection using direct module imports (no MCP protocol)."""

    def __init__(self, module_path: str, server_instance=None):
        super().__init__()
        self.module_path = module_path
        self.server = server_instance
        self._module = None

    def _load_module(self):
        """Load the server module."""
        import importlib

        if not self._module:
            self._module = importlib.import_module(self.module_path)
        return self._module

    def list_tools(self) -> List[Dict[str, Any]]:
        """Retrieve available tools from the module."""
        module = self._load_module()

        if hasattr(module, "list_tools"):
            return module.list_tools()
        if hasattr(module, "get_tools"):
            return module.get_tools()
        if hasattr(module, "tools"):
            return module.tools

        return []

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool directly on the module."""
        module = self._load_module()

        # Try module-level function
        if hasattr(module, tool_name):
            func = getattr(module, tool_name)
            if callable(func):
                return func(**arguments)

        # Try call_tool function
        if hasattr(module, "call_tool"):
            return module.call_tool(tool_name, arguments)

        raise ValueError(f"Tool '{tool_name}' not found in module '{self.module_path}'")


def create_connection(
    transport: str,
    command: str = None,
    args: List[str] = None,
    env: Dict[str, str] = None,
    url: str = None,
    headers: Dict[str, str] = None,
    module_path: str = None,
) -> ConnectionBase:
    """
    Factory function to create the appropriate connection.

    Args:
        transport: Connection type ("stdio" or "direct")
        command: Command to run (stdio only)
        args: Command arguments (stdio only)
        env: Environment variables (stdio only)
        url: Server URL (not used in script-based mode)
        headers: HTTP headers (not used in script-based mode)
        module_path: Module path for direct import

    Returns:
        Connection instance
    """
    transport = transport.lower()

    if transport == "stdio":
        if not command:
            raise ValueError("Command is required for stdio transport")
        return StdioConnection(command=command, args=args, env=env)

    elif transport == "direct":
        if not module_path:
            raise ValueError("Module path is required for direct transport")
        return DirectConnection(module_path=module_path)

    elif transport in ["mcp", "sse", "http"]:
        raise ValueError(
            f"Transport '{transport}' requires MCP protocol. "
            "Use 'stdio' or 'direct' for script-based evaluation."
        )

    else:
        raise ValueError(f"Unsupported transport type: {transport}. Use 'stdio' or 'direct'")


def main():
    """CLI interface for connection testing."""
    import argparse

    parser = argparse.ArgumentParser(description="Test connections to media-poster servers")
    parser.add_argument("-t", "--transport", choices=["stdio", "direct"], default="stdio")
    parser.add_argument("-c", "--command", help="Server command (stdio)")
    parser.add_argument("-a", "--args", nargs="+", help="Command arguments")
    parser.add_argument("-m", "--module", help="Module path (direct)")

    args = parser.parse_args()

    try:
        if args.transport == "stdio" and args.command:
            conn = create_connection("stdio", command=args.command, args=args.args)
        elif args.transport == "direct" and args.module:
            conn = create_connection("direct", module_path=args.module)
        else:
            parser.print_help()
            return

        tools = conn.list_tools()
        print(f"Found {len(tools)} tools:")
        for tool in tools:
            print(f"  - {tool.get('name', 'unknown')}")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
