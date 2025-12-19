"Friday MCP Integration - Model Context Protocol Client Manager"

import asyncio
import os
import json
import shutil
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from contextlib import AsyncExitStack

from rich.console import Console
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, TextContent, ImageContent, EmbeddedResource

console = Console()

@dataclass
class MCPServerConfig:
    command: str
    args: List[str]
    env: Dict[str, str] = None

class MCPManager:
    """Manages MCP server connections and tools"""
    
    def __init__(self, config_path: str = "~/.friday/mcp.json"):
        self.config_path = os.path.expanduser(config_path)
        self.servers: Dict[str, MCPServerConfig] = {}
        self.sessions: Dict[str, ClientSession] = {}
        self.exit_stack = AsyncExitStack()
        self.available_tools: List[Dict[str, Any]] = []
        self._load_config()

    def _load_config(self):
        """Load server configuration"""
        if not os.path.exists(self.config_path):
            return
        
        try:
            with open(self.config_path, "r") as f:
                data = json.load(f)
                for name, cfg in data.items():
                    self.servers[name] = MCPServerConfig(
                        command=cfg["command"],
                        args=cfg.get("args", []),
                        env=cfg.get("env", {})
                    )
        except Exception as e:
            console.print(f"[red]Failed to load MCP config: {e}[/red]")

    def save_config(self):
        """Save server configuration"""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        data = {name: asdict(cfg) for name, cfg in self.servers.items()}
        try:
            with open(self.config_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            console.print(f"[red]Failed to save MCP config: {e}[/red]")

    async def connect_all(self):
        """Connect to all configured servers"""
        for name in self.servers:
            try:
                await self.connect_server(name)
            except Exception as e:
                console.print(f"[red]Failed to connect to MCP server '{name}': {e}[/red]")

    async def connect_server(self, name: str):
        """Connect to a specific server"""
        if name not in self.servers:
            raise ValueError(f"Server '{name}' not found in config")
        
        if name in self.sessions:
            return # Already connected

        cfg = self.servers[name]
        
        # Prepare environment
        env = os.environ.copy()
        if cfg.env:
            env.update(cfg.env)

        server_params = StdioServerParameters(
            command=cfg.command,
            args=cfg.args,
            env=env
        )

        try:
            # We need to maintain the context manager for the session
            # using AsyncExitStack to keep it alive
            stdio_ctx = stdio_client(server_params)
            read, write = await self.exit_stack.enter_async_context(stdio_ctx)
            session = await self.exit_stack.enter_async_context(ClientSession(read, write))
            
            await session.initialize()
            self.sessions[name] = session
            
            # Fetch tools
            tools_result = await session.list_tools()
            for tool in tools_result.tools:
                self.available_tools.append({
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema,
                    "server": name
                })
            
            console.print(f"[green]Connected to MCP server: {name}[/green]")
            
        except Exception as e:
            console.print(f"[red]Error connecting to {name}: {e}[/red]")
            raise

    async def cleanup(self):
        """Close all connections"""
        await self.exit_stack.aclose()
        self.sessions.clear()
        self.available_tools.clear()

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Call a tool on the appropriate server"""
        # Find which server has this tool
        tool_info = next((t for t in self.available_tools if t["name"] == tool_name), None)
        if not tool_info:
            return f"Error: Tool '{tool_name}' not found"
        
        server_name = tool_info["server"]
        session = self.sessions.get(server_name)
        if not session:
            return f"Error: Server '{server_name}' not connected"

        try:
            result: CallToolResult = await session.call_tool(tool_name, arguments)
            
            output = []
            for content in result.content:
                if isinstance(content, TextContent):
                    output.append(content.text)
                elif isinstance(content, ImageContent):
                    output.append(f"[Image: {content.mimeType}]")
                elif isinstance(content, EmbeddedResource):
                    output.append(f"[Resource: {content.resource.uri}]")
            
            return "\n".join(output)
        except Exception as e:
            return f"Error executing tool '{tool_name}': {e}"

    def add_server(self, name: str, command: str, args: List[str] = None, env: Dict[str, str] = None):
        """Add a new server to config"""
        self.servers[name] = MCPServerConfig(command, args or [], env or {})
        self.save_config()

    def remove_server(self, name: str):
        """Remove a server from config"""
        if name in self.servers:
            del self.servers[name]
            self.save_config()
