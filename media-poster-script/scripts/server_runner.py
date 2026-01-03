#!/usr/bin/env python3
"""
Server Runner - Manage local server processes for evaluation.

This module provides process management for running MCP servers
as standalone subprocesses without MCP protocol connections.
"""

import asyncio
import json
import subprocess
from contextlib import AsyncExitStack, contextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, ContextManager, Dict, List, Optional


class ServerRunner:
    """Manages a server process for local tool execution."""

    def __init__(
        self,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        working_dir: Optional[Path] = None,
    ):
        """
        Initialize the server runner.

        Args:
            command: Executable command to run the server
            args: Arguments to pass to the command
            env: Environment variables for the server
            working_dir: Working directory for the server process
        """
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.working_dir = working_dir
        self._process: Optional[subprocess.Popen] = None
        self._stack: Optional[AsyncExitStack] = None

    @contextmanager
    def run(self) -> ContextManager[Optional[subprocess.Popen]]:
        """
        Context manager to run the server process.

        Yields:
            The Popen process instance
        """
        import os

        env = os.environ.copy()
        env.update(self.env)

        try:
            self._process = subprocess.Popen(
                [self.command] + self.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                cwd=self.working_dir,
            )
            yield self._process
        finally:
            if self._process and self._process.poll() is None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait()
            self._process = None

    async def run_async(self) -> None:
        """Start the server process asynchronously."""
        import os

        env = os.environ.copy()
        env.update(self.env)

        self._stack = AsyncExitStack()
        await self._stack.__aenter__()

        self._process = await self._stack.enter_async_context(
            asyncio.subprocess.create_subprocess_exec(
                self.command,
                *self.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=self.working_dir,
            )
        )

    async def __aenter__(self):
        """Async context manager entry."""
        await self.run_async()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._stack:
            await self._stack.__aexit__(exc_type, exc_val, exc_tb)
        self._process = None
        self._stack = None

    def send_tool_call(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a tool call to the server via stdin.

        This is a simple JSON-RPC-like interface for local servers
        that read from stdin and write JSON to stdout.

        Args:
            tool_name: Name of the tool to call
            args: Arguments to pass to the tool

        Returns:
            Parsed JSON response from the server
        """
        if not self._process:
            raise RuntimeError("Server process not running")

        request = json.dumps({"tool": tool_name, "args": args})
        self._process.stdin.write(request + "\n")
        self._process.stdin.flush()

        # Read response
        response_line = self._process.stdout.readline()
        return json.loads(response_line)

    async def send_tool_call_async(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Async version of send_tool_call."""
        if not self._process:
            raise RuntimeError("Server process not running")

        request = json.dumps({"tool": tool_name, "args": args}) + "\n"
        self._process.stdin.write(request)
        await self._process.stdin.drain()

        response_line = await self._process.stdout.readline()
        return json.loads(response_line)

    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Request the list of available tools from the server.

        Returns:
            List of tool definitions
        """
        if not self._process:
            raise RuntimeError("Server process not running")

        request = json.dumps({"action": "list_tools"}) + "\n"
        self._process.stdin.write(request)
        self._process.stdin.flush()

        response_line = self._process.stdout.readline()
        return json.loads(response_line)


class DirectToolCaller:
    """Call tools directly through Python imports for importable servers."""

    def __init__(self, module_path: str, server_instance=None):
        """
        Initialize with server module path.

        Args:
            module_path: Dot-separated path to server module (e.g., "media_poster.server")
            server_instance: Pre-instantiated server object (optional)
        """
        self.module_path = module_path
        self.server = server_instance
        self._module = None

    def _load_module(self):
        """Load the server module."""
        import importlib

        if not self._module:
            self._module = importlib.import_module(self.module_path)
        return self._module

    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Get available tools from the server.

        Returns:
            List of tool definitions with name, description, and input_schema
        """
        module = self._load_module()

        # Try different common patterns for tool listing
        if hasattr(module, "list_tools"):
            return module.list_tools()
        elif hasattr(module, "get_tools"):
            return module.get_tools()
        elif hasattr(module, "tools"):
            return module.tools
        else:
            # Fallback: try to discover tools from server methods
            server = self.server or (module.Server() if hasattr(module, "Server") else None)
            if server:
                return self._discover_tools(server)
            return []

    def _discover_tools(self, server) -> List[Dict[str, Any]]:
        """Discover tools by inspecting server methods."""
        tools = []
        for attr_name in dir(server):
            if attr_name.startswith("_"):
                continue
            attr = getattr(server, attr_name)
            if callable(attr):
                # Check if it looks like a tool (not internal methods)
                tools.append({
                    "name": attr_name,
                    "description": getattr(attr, "__doc__", f"Tool: {attr_name}") or f"Tool: {attr_name}",
                    "input_schema": getattr(attr, "input_schema", {"type": "object", "properties": {}}),
                })
        return tools

    def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """
        Call a tool directly on the server.

        Args:
            tool_name: Name of the tool to call
            args: Arguments to pass to the tool

        Returns:
            Tool execution result
        """
        module = self._load_module()

        # Try different calling patterns
        if self.server:
            # Call on pre-instantiated server
            attr = getattr(self.server, tool_name, None)
            if callable(attr):
                return attr(**args)

        # Try module-level function
        attr = getattr(module, tool_name, None)
        if callable(attr):
            return attr(**args)

        # Try module-level call_tool function
        if hasattr(module, "call_tool"):
            return module.call_tool(tool_name, args)

        raise ValueError(f"Tool '{tool_name}' not found in module '{self.module_path}'")


def create_server_runner(
    command: str = None,
    args: List[str] = None,
    env: Dict[str, str] = None,
    module_path: str = None,
    server_instance=None,
) -> ServerRunner:
    """
    Factory function to create the appropriate server runner.

    Args:
        command: Executable command for subprocess mode
        args: Command arguments
        env: Environment variables
        module_path: Module path for direct import mode
        server_instance: Pre-instantiated server

    Returns:
        ServerRunner or DirectToolCaller instance
    """
    if module_path:
        return DirectToolCaller(module_path, server_instance)
    elif command:
        return ServerRunner(command=command, args=args, env=env)
    else:
        raise ValueError("Either 'command' or 'module_path' must be provided")


def main():
    """CLI interface for server runner."""
    import argparse

    parser = argparse.ArgumentParser(description="Run server process for evaluation")
    parser.add_argument("command", help="Command to run")
    parser.add_argument("--args", nargs="+", help="Command arguments")
    parser.add_argument("--env", nargs="+", help="Environment variables KEY=VALUE")

    args = parser.parse_args()

    env = {}
    if args.env:
        for env_var in args.env:
            if "=" in env_var:
                key, value = env_var.split("=", 1)
                env[key.strip()] = value.strip()

    runner = ServerRunner(command=args.command, args=args.args, env=env)

    print(f"Starting server: {args.command} {' '.join(args.args or [])}")
    with runner.run() as process:
        print(f"Server started with PID: {process.pid}")
        print("Press Ctrl+C to stop...")

        try:
            while process.poll() is None:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping server...")


if __name__ == "__main__":
    main()
