"Friday CLI - Main conversational interface with compounding support"

import os
import signal
import asyncio # New import

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import HTML
import random

from friday.theme import FRIDAY_THEME, get_prompt_style, get_rich_theme, ASCII_ART
from friday.tools import ToolExecutor
from friday.context import ConversationContext
from friday.agent import FridayAgent
from friday.mcp import MCPManager # New Import

# Compounding Engineering Imports
try:
    from config import configure_dspy
    from workflows.codify import run_codify
    from workflows.generate_command import run_generate_command
    from workflows.plan import run_plan
    from workflows.review import run_review
    from workflows.triage import run_triage
    from workflows.work import run_unified_work
    from utils.knowledge_base import KnowledgeBase
except ImportError as e:
    # Handle case where dependencies aren't available
    import sys
    print(f"DEBUG: Import failed in friday/cli.py: {e}", file=sys.stderr)
    configure_dspy = None


class FridayCLI:
    """Main Friday CLI application"""

    def __init__(self):
        # Configure DSPy for compounding commands
        if configure_dspy:
            try:
                configure_dspy()
            except Exception as e:
                # Use a temporary console since self.console isn't init'd yet
                Console().print(f"[yellow]Warning: Failed to configure DSPy: {e}[/]")

        self.workflows = {}  # Store compound workflows: {workflow_name: [commands]}
        # Load user config (~/.friday/config.json)
        self.user_config = self._load_user_config()

        # Determine theme profile from env or config
        theme_profile = os.getenv("FRIDAY_THEME_PROFILE") or (self.user_config.get("theme") if isinstance(self.user_config, dict) else None) or "dark"

        self.console = Console(theme=get_rich_theme(theme_profile), force_terminal=True)
        self.context = ConversationContext()
        self.tools = ToolExecutor(self.console)
        self.mcp_manager = MCPManager() # Initialize MCPManager
        self.agent = FridayAgent(self.console, self.tools, self.context, mcp_manager=self.mcp_manager) # Pass mcp_manager to agent
        self.running = True
        
        history_dir = os.path.expanduser("~/.friday")
        os.makedirs(history_dir, exist_ok=True)
        history_file = os.path.join(history_dir, "history")
        
        commands = [
            '/help', '/clear', '/context', '/history', '/compact',
            '/exit', '/quit', '/model', '/diff', '/status', '/files',
            '/compound', '/compound init', '/compound add', '/compound list',
            '/compound run', '/compound remove', '/compound clear',
            '/mcp', '/mcp add', '/mcp remove', '/mcp list', '/mcp connect' # Add MCP commands
        ]
        
        # Add compounding commands if available
        if configure_dspy:
            commands.extend([
                '/triage', '/plan', '/work', '/review', 
                '/generate', '/codify', '/compress'
            ])
            
        command_completer = WordCompleter(commands, ignore_case=True)
        
        def bottom_toolbar():
            # Show context stats in toolbar
            turn_count = len([m for m in self.context.messages if m.get("role") == "user"])
            file_count = len(self.context.files_mentioned)
            return HTML(f"<b><style bg='ansiblack' fg='ansicyan'> /help </style> <style fg='ansigray'>·</style> <style fg='ansigreen'>Ctrl+C</style> cancel <style fg='ansigray'>·</style> <style fg='ansired'>Ctrl+D</style> exit <style fg='ansigray'>│</style> <style fg='ansigray'>Turn {turn_count} · {file_count} files</style></b>")

        def make_rprompt():
            provider = os.getenv("DSPY_LM_PROVIDER", "openai")
            model = os.getenv("DSPY_LM_MODEL", "gpt-4o")
            # Shorten common model names
            model_short = model.replace("gpt-4o", "gpt-4o").replace("claude-3-5-sonnet", "claude-3.5")
            return HTML(f"<style fg='ansigray'>{provider}/{model_short}</style>")

        self.session = PromptSession(
            history=FileHistory(history_file),
            auto_suggest=AutoSuggestFromHistory(),
            style=get_prompt_style(os.getenv("FRIDAY_THEME_PROFILE") or (self.user_config.get("theme") if isinstance(self.user_config, dict) else None)),
            multiline=False,
            key_bindings=self._create_key_bindings(),
            completer=command_completer,
            complete_while_typing=True,
            bottom_toolbar=bottom_toolbar,
        )
        self._make_rprompt = make_rprompt
        
        signal.signal(signal.SIGINT, self._handle_interrupt)

    def _create_key_bindings(self) -> KeyBindings:
        """Create custom key bindings"""
        kb = KeyBindings()
        
        @kb.add('c-c')
        def _(event):
            """Handle Ctrl+C"""
            event.app.exit(result=None)
        
        @kb.add('c-d')
        def _(event):
            """Handle Ctrl+D to exit"""
            self.running = False
            event.app.exit(result='/exit')
        
        return kb

    def _handle_interrupt(self, signum, frame):
        """Handle interrupt signal gracefully"""
        self.console.print("\n[dim]Use /exit or Ctrl+D to quit[/dim]")

    def _load_user_config(self):
        """Load user config from ~/.friday/config.json if present"""
        import json
        cfg_path = os.path.expanduser("~/.friday/config.json")
        if not os.path.exists(cfg_path):
            return {}
        try:
            with open(cfg_path, "r") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _print_banner(self):
        """Print the welcome banner with optional ASCII art.
        Controlled by env vars:
          - FRIDAY_NO_BANNER=1 -> skip all banner output
          - FRIDAY_MINIMAL=1   -> no ASCII art / tips, compact panel
        """
        # Feature toggles from env and ~/.friday/config.json
        def _is_true(val: str | None) -> bool:
            return str(val or "").strip().lower() in {"1", "true", "yes", "on"}

        # Read env first; fall back to config
        env_no_banner = os.getenv("FRIDAY_NO_BANNER")
        env_minimal = os.getenv("FRIDAY_MINIMAL")
        env_ascii_variant = os.getenv("FRIDAY_ASCII_VARIANT")  # block|compact

        cfg_banner = (self.user_config or {}).get("banner", {}) if hasattr(self, "user_config") else {}
        cfg_enabled = cfg_banner.get("enabled", True)
        cfg_minimal = cfg_banner.get("minimal", False)
        cfg_ascii_variant = cfg_banner.get("ascii", "compact")

        if _is_true(env_no_banner) or (env_no_banner is None and not cfg_enabled):
            return

        minimal_mode = _is_true(env_minimal) if env_minimal is not None else bool(cfg_minimal)
        ascii_variant = (env_ascii_variant or cfg_ascii_variant or "block").lower()

        try:
            from friday import __version__ as friday_version
        except Exception:
            friday_version = ""

        tips = [
            "Use /help to discover commands",
            "Press Ctrl+C to cancel current operation",
            "Press Ctrl+D or type /exit to quit",
            "Use /files **/*.py to list Python files",
            "Try /status or /diff to check Git state",
            "/plan turns ideas into actionable plans",
        ]
        tip = random.choice(tips)

        # Choose ASCII art variant
        if ascii_variant == "compact":
            ascii_art = f"""
[bold blue]
{ASCII_ART.get("friday", "FRIDAY")}
[/]
"""
        else:
            ascii_art = """
[bold blue]
███████╗██████╗ ██╗ ██████╗  █████╗ ██╗   ██╗
██╔════╝██╔══██╗██║██╔════╝ ██╔══██╗╚██╗ ██╔╝
█████╗  ██████╔╝██║██║  ███╗███████║ ╚████╔╝ 
██╔══╝  ██╔══██╗██║██╔══██║  ╚██╔╝  
███████╗██║  ██║██║╚██████╔╝██║  ██║   ██║   
╚══════╝╚═╝  ╚═╝╚═╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝   
[/]
"""
        header = f"[bold white]FRIDAY[/] [dim]v{friday_version}[/]" if friday_version else "[bold white]FRIDAY[/]"

        # Build adaptive banner using Rich Panel
        if minimal_mode:
            body = "\n".join([
                f"{header}",
                "[cyan]AI-Powered Coding Assistant[/]",
                "[green]/help[/]  [dim]Commands[/]  [green]/clear[/]  [dim]Clear[/]  [green]/exit[/]  [dim]Quit[/]",
            ])
            # Minimal: no ASCII art, compact body
            self.console.print(Panel.fit(body, border_style="blue"))
        else:
            body = "\n".join([
                f"{header}",
                "[cyan]AI-Powered Coding Assistant[/]",
                "",
                f"[dim]{tip}[/]",
                "[green]/help[/]  [dim]Show available commands[/]",
                "[green]/clear[/] [dim]Clear conversation[/]",
                "[green]/exit[/]  [dim]Exit Friday[/]",
            ])
            # Print ASCII art followed by adaptive panel
            self.console.print(ascii_art)
            self.console.print(Panel.fit(body, border_style="blue"))

        cwd = os.getcwd()
        self.console.print(f"[dim]Working directory:[/] [cyan]{cwd}[/]")
        self.console.print()

    def _print_help(self):
        """Print help information"""
        help_text = """
[bold]Commands:[/]
  [green]/help[/]              Show this help message
  [green]/clear[/]             Clear conversation history
  [green]/context[/]           Show current context (files, git status)
  [green]/history[/]           Show conversation history
  [green]/compact[/]           Compact/summarize conversation history
  [green]/model[/]             Show/change LLM model
  [green]/diff[/]              Show git diff
  [green]/status[/]            Show git status
  [green]/files[/] [pattern]    List files matching pattern
  [green]/compound[/]          Manage compound workflows
  [green]/mcp[/]               Manage Model Context Protocol servers
  [green]/exit[/], [green]/quit[/]       Exit Friday

[bold]Compounding Commands:[/]
  [green]/triage[/]            Triage and categorize findings
  [green]/plan[/] <desc>       Transform description into project plan
  [green]/work[/] <pattern>    Execute work (ID, plan file, or pattern)
  [green]/review[/] [target]   Review PR or local changes
  [green]/generate[/] <desc>   Generate a new CLI command
  [green]/codify[/] <feedback> Codify feedback into knowledge base
  [green]/compress[/]          Compress knowledge base (AI.md)

[bold]Capabilities:[/]
  [cyan]•[/] Read and edit files with syntax highlighting
  [cyan]•[/] Search codebase (grep, glob patterns)
  [cyan]•[/] Execute shell commands safely
  [cyan]•[/] Git operations (status, diff, log, commit)
  [cyan]•[/] Create and manage project todos
  [cyan]•[/] Generate feature plans and code reviews
  [cyan]•[/] Explain and refactor code

[bold]Examples:[/]
  [dim]›[/] "Read the main.py file and explain what it does"
  [dim]›[/] "/plan Add a new user authentication system"
  [dim]›[/] "/work p1"
  [dim]›[/] "/codify Always use type hints in Python functions"
  [dim]›[/] "/compound run my-workflow"
  [dim]›[/] "!ls -la" (Execute shell command)

[bold]Tips:[/]
  [dim]•[/] Be specific about file paths and function names
  [dim]•[/] Ask follow-up questions for clarification
  [dim]•[/] Use Ctrl+C to cancel, Ctrl+D to exit
"""
        self.console.print(Panel(help_text, title="[bold]Friday Help[/]", border_style="blue"))

    def _print_context(self):
        """Print current context information"""
        import subprocess
        
        table = Table(title="Current Context", border_style="blue")
        table.add_column("Item", style="cyan")
        table.add_column("Value", style="white")
        
        table.add_row("Working Directory", os.getcwd())
        
        try:
            branch = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, timeout=5
            ).stdout.strip()
            table.add_row("Git Branch", branch)
        except Exception:
            table.add_row("Git Branch", "[dim]Not a git repo[/dim]")
        
        try:
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, timeout=5
            ).stdout
            changed = len([line for line in status.strip().split('\n') if line])
            table.add_row("Changed Files", str(changed))
        except Exception:
            pass
        
        table.add_row("Conversation Turns", str(len(self.context.messages)))
        table.add_row("Files in Context", str(len(self.context.files_mentioned)))
        
        provider = os.getenv("DSPY_LM_PROVIDER", "openai")
        model = os.getenv("DSPY_LM_MODEL", "gpt-4o")
        table.add_row("LLM Provider", f"{provider}/{model}")
        
        self.console.print(table)

    def _print_history(self):
        """Print conversation history"""
        if not self.context.messages:
            self.console.print("[dim]No conversation history yet[/dim]")
            return
        
        for i, msg in enumerate(self.context.messages[-10:], 1):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")[:200]
            
            if role == "user":
                self.console.print(f"[bold cyan]You:[/] {content}")
            else:
                self.console.print(f"[bold green]Friday:[/] {content}...")
            self.console.print()

    async def _handle_command(self, command: str) -> bool: # Made async
        """Handle slash commands. Returns True if should continue, False to exit."""
        parts = command.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        # Standard Commands
        if cmd in ["/exit", "/quit", "/q"]:
            self.console.print("\n[bold blue]Goodbye! Happy coding![/]")
            return False
        elif cmd == "/help":
            self._print_help()
        elif cmd == "/clear":
            self.context.clear()
            self.console.print("[green]Conversation cleared[/]")
        elif cmd == "/context":
            self._print_context()
        elif cmd == "/history":
            self._print_history()
        elif cmd == "/compact":
            self.context.compact()
            self.console.print("[green]Conversation history compacted[/]")
        elif cmd == "/model":
            self._show_model_info()
        elif cmd == "/diff":
            self.tools.git_diff(args or "HEAD")
        elif cmd == "/status":
            self.tools.git_status()
        elif cmd == "/files":
            pattern = args or "*"
            self.tools.list_directory(".", pattern)
        elif cmd == "/compound":
            self._handle_compound_command(args)
        
        # Compounding Commands
        elif cmd == "/triage":
            self._run_safe(run_triage)
        elif cmd == "/plan":
            if not args:
                self.console.print("[yellow]Usage: /plan <feature description>[/]")
            else:
                self._run_safe(run_plan, args)
        elif cmd == "/work":
            self._run_safe(run_unified_work, pattern=args if args else None)
        elif cmd == "/review":
            self._run_safe(run_review, args if args else "latest")
        elif cmd in ["/generate", "/generate-command"]:
            if not args:
                self.console.print("[yellow]Usage: /generate <description>[/]")
            else:
                self._run_safe(run_generate_command, description=args)
        elif cmd == "/codify":
            if not args:
                self.console.print("[yellow]Usage: /codify <feedback>[/]")
            else:
                self._run_safe(run_codify, feedback=args)
        elif cmd in ["/compress", "/compress-kb"]:
            kb = KnowledgeBase()
            self._run_safe(kb.compress_ai_md)
            
        else:
            self.console.print(f"[yellow]Unknown command: {command}[/]")
            self.console.print("[dim]Type /help for available commands[/dim]")
        
        return True

    def _run_safe(self, func, *args, **kwargs):
        """Run a workflow function safely"""
        if not configure_dspy:
             self.console.print("[red]Error: Compounding commands are not available (imports failed).[/]")
             return
             
        try:
            func(*args, **kwargs)
        except Exception as e:
            self.console.print(f"[red]Error executing workflow: {e}[/]")

    async def _handle_mcp_command(self, args: str): # New async method
        """Handle /mcp commands"""
        parts = args.strip().split(maxsplit=1)
        if not parts:
            self.console.print("[yellow]Usage: /mcp <subcommand> [args][/]")
            self.console.print("[dim]Subcommands: add, remove, list, connect[/dim]")
            return
        
        subcommand = parts[0].lower()
        sub_args = parts[1] if len(parts) > 1 else ""
        
        if subcommand == "add":
            self._mcp_add_server(sub_args)
        elif subcommand == "remove":
            self._mcp_remove_server(sub_args)
        elif subcommand == "list":
            self._mcp_list_servers()
        elif subcommand == "connect":
            await self._mcp_connect_server(sub_args)
        else:
            self.console.print(f"[yellow]Unknown /mcp subcommand: {subcommand}[/]")
            self.console.print("[dim]Available: add, remove, list, connect[/dim]")

    def _mcp_add_server(self, args: str):
        """Add an MCP server to configuration: /mcp add <name> <command> [args...]"""
        parts = args.strip().split(maxsplit=2)
        if len(parts) < 2:
            self.console.print("[yellow]Usage: /mcp add <name> <command> [args...][/]")
            return
        
        name = parts[0]
        command = parts[1]
        cmd_args = parts[2].split() if len(parts) > 2 else []
        
        self.mcp_manager.add_server(name, command, cmd_args)
        self.console.print(f"[green]MCP server '{name}' added.[/green]")

    def _mcp_remove_server(self, name: str):
        """Remove an MCP server from configuration: /mcp remove <name>"""
        if not name:
            self.console.print("[yellow]Usage: /mcp remove <name>[/]")
            return
        
        if name not in self.mcp_manager.servers:
            self.console.print(f"[yellow]Error: Server '{name}' not found.[/yellow]")
            return
        
        # Disconnect if connected
        if name in self.mcp_manager.sessions:
            # Need to figure out how to disconnect specific session cleanly
            # For now, just remove from config
            pass 
        
        self.mcp_manager.remove_server(name)
        self.console.print(f"[green]MCP server '{name}' removed.[/green]")

    def _mcp_list_servers(self):
        """List configured MCP servers: /mcp list"""
        if not self.mcp_manager.servers:
            self.console.print("[dim]No MCP servers configured.[/dim]")
            return
        
        table = Table(title="Configured MCP Servers", border_style="blue")
        table.add_column("Name", style="cyan")
        table.add_column("Command", style="white")
        table.add_column("Status", style="green")
        
        for name, cfg in self.mcp_manager.servers.items():
            status = "Connected" if name in self.mcp_manager.sessions else "Disconnected"
            table.add_row(name, f"{cfg.command} {' '.join(cfg.args)}", status)
            
        self.console.print(table)
        
        if self.mcp_manager.available_tools:
            self.console.print("\n[bold]Available MCP Tools:[/]")
            for tool in self.mcp_manager.available_tools:
                self.console.print(f"  - {tool['name']} (from {tool['server']})")

    async def _mcp_connect_server(self, name: str):
        """Connect to a specific MCP server: /mcp connect <name>"""
        if not name:
            self.console.print("[yellow]Usage: /mcp connect <name>[/]")
            return
        
        if name not in self.mcp_manager.servers:
            self.console.print(f"[yellow]Error: Server '{name}' not found in config.[/yellow]")
            return
        
        self.console.print(f"[cyan]Connecting to MCP server '{name}'...[/cyan]")
        try:
            await self.mcp_manager.connect_server(name)
            self.console.print(f"[green]Successfully connected to '{name}'.[/green]")
        except Exception as e:
            self.console.print(f"[red]Failed to connect to '{name}': {e}[/red]")

    async def _handle_compound_command(self, args: str): # Made async
        """Handle compound workflow commands"""
        parts = args.strip().split(maxsplit=1)
        if not parts:
            self.console.print("[yellow]Usage: /compound <subcommand> [args][/]")
            self.console.print("[dim]Subcommands: init, add, list, run, remove, clear[/dim]")
            return
        
        subcommand = parts[0].lower()
        sub_args = parts[1] if len(parts) > 1 else ""
        
        if subcommand == "init":
            self._compound_init(sub_args)
        elif subcommand == "add":
            self._compound_add(sub_args)
        elif subcommand == "list":
            self._compound_list(sub_args)
        elif subcommand == "run":
            await self._compound_run(sub_args)
        elif subcommand == "remove":
             self._compound_remove(sub_args)
        elif subcommand == "clear":
             self._compound_clear(sub_args)
        else:
            self.console.print(f"[yellow]Unknown compound subcommand: {subcommand}[/]")
            self.console.print("[dim]Available: init, add, list, run, remove, clear[/dim]")

    def _compound_init(self, workflow_name: str):
        """Initialize a new compound workflow"""
        if not workflow_name:
            self.console.print("[yellow]Error: Workflow name is required[/]")
            self.console.print("[dim]Usage: /compound init <workflow_name>[/dim]")
            return
        
        if workflow_name in self.workflows:
            self.console.print(f"[yellow]Error: Workflow '{workflow_name}' already exists[/]")
            return
        
        self.workflows[workflow_name] = []
        self.console.print(f"[green]Workflow '{workflow_name}' initialized[/]")

    def _compound_add(self, args: str):
        """Add a command to a compound workflow"""
        parts = args.strip().split(maxsplit=1)
        if len(parts) < 2:
            self.console.print("[yellow]Error: Workflow name and command are required[/]")
            self.console.print("[dim]Usage: /compound add <workflow_name> <command>[/dim]")
            return
        
        workflow_name, command = parts[0], parts[1]
        
        if workflow_name not in self.workflows:
            self.console.print(f"[yellow]Error: Workflow '{workflow_name}' does not exist[/]")
            return
        
        self.workflows[workflow_name].append(command)
        self.console.print(f"[green]Command added to workflow '{workflow_name}'[/]")

    def _compound_list(self, workflow_name: str):
        """List commands in a compound workflow"""
        if not workflow_name:
            # List all workflows
            if not self.workflows:
                self.console.print("[dim]No workflows defined[/dim]")
                return
            
            self.console.print("[bold]Available Workflows:[/]")
            for name in self.workflows.keys():
                count = len(self.workflows[name])
                self.console.print(f"  [cyan]{name}[/] ({count} commands)")
            return
        
        if workflow_name not in self.workflows:
            self.console.print(f"[yellow]Error: Workflow '{workflow_name}' does not exist[/]")
            return
        
        commands = self.workflows[workflow_name]
        if not commands:
            self.console.print(f"[dim]Workflow '{workflow_name}' is empty[/dim]")
            return
        
        self.console.print(f"[bold]Workflow '{workflow_name}':[/]")
        for i, cmd in enumerate(commands, 1):
            self.console.print(f"  {i}. [white]{cmd}[/]")

    async def _compound_run(self, workflow_name: str):
        """Run all commands in a compound workflow"""
        if not workflow_name:
            self.console.print("[yellow]Error: Workflow name is required[/]")
            self.console.print("[dim]Usage: /compound run <workflow_name>[/dim]")
            return
        
        if workflow_name not in self.workflows:
            self.console.print(f"[yellow]Error: Workflow '{workflow_name}' does not exist[/]")
            return
        
        commands = self.workflows[workflow_name]
        if not commands:
            self.console.print(f"[dim]Workflow '{workflow_name}' is empty[/dim]")
            return
        
        self.console.print(f"[bold]Running workflow '{workflow_name}'...[/]")
        
        for i, cmd in enumerate(commands, 1):
            self.console.print(f"[dim]Executing command {i}/{len(commands)}:[/] [white]{cmd}[/]")
            try:
                # Execute the command through the agent
                await self.agent.process_message(cmd) # Await process_message
            except Exception as e:
                self.console.print(f"[red]Error executing command {i}: {e}[/]")
                break
        
        self.console.print(f"[green]Workflow '{workflow_name}' completed[/]")

    def _compound_remove(self, args: str):
        """Remove a command from a compound workflow"""
        parts = args.strip().split(maxsplit=1)
        if len(parts) < 2:
            self.console.print("[yellow]Error: Workflow name and command index are required[/]")
            self.console.print("[dim]Usage: /compound remove <workflow_name> <index>[/dim]")
            return
        
        workflow_name, index_str = parts[0], parts[1]
        
        try:
            index = int(index_str) - 1  # Convert to 0-based index
        except ValueError:
            self.console.print("[yellow]Error: Index must be a number[/]")
            return
        
        if workflow_name not in self.workflows:
            self.console.print(f"[yellow]Error: Workflow '{workflow_name}' does not exist[/]")
            return
        
        commands = self.workflows[workflow_name]
        if index < 0 or index >= len(commands):
            self.console.print("[yellow]Error: Invalid command index[/]")
            return
        
        removed_cmd = commands.pop(index)
        self.console.print(f"[green]Removed command from workflow '{workflow_name}': {removed_cmd}[/]")

    def _compound_clear(self, workflow_name: str):
        """Clear all commands from a compound workflow"""
        if not workflow_name:
            self.console.print("[yellow]Error: Workflow name is required[/]")
            self.console.print("[dim]Usage: /compound clear <workflow_name>[/dim]")
            return
        
        if workflow_name not in self.workflows:
            self.console.print(f"[yellow]Error: Workflow '{workflow_name}' does not exist[/]")
            return
        
        self.workflows[workflow_name] = []
        self.console.print(f"[green]Workflow '{workflow_name}' cleared[/]")

    def _show_model_info(self):
        """Show current LLM model information"""
        provider = os.getenv("DSPY_LM_PROVIDER", "openai")
        model = os.getenv("DSPY_LM_MODEL", "gpt-4o")
        
        self.console.print("[bold]Current Model:[/]")
        self.console.print(f"  Provider: [cyan]{provider}[/]")
        self.console.print(f"  Model: [cyan]{model}[/]")
        self.console.print()
        self.console.print("[dim]To change, set environment variables:[/]")
        self.console.print("[dim]  DSPY_LM_PROVIDER=openai|anthropic|openrouter[/]")
        self.console.print("[dim]  DSPY_LM_MODEL=gpt-4o|claude-3-5-sonnet-20241022|etc[/]")

    def _get_prompt(self) -> str:
        """Get the input prompt with current directory and context"""
        cwd = os.path.basename(os.getcwd())
        
        # Add conversation turn indicator
        turn = len([m for m in self.context.messages if m.get("role") == "user"])
        
        # Color-code prompt based on context size
        if turn > 40:
            turn_color = "warning"
        elif turn > 20:
            turn_color = "info"
        else:
            turn_color = "muted"
        
        return f"[prompt.path]{cwd}[/] [{turn_color}]#{turn}[/] [prompt.arrow]›[/] "

    async def run(self): # Made async
        """Main run loop"""
        self._print_banner()
        
        # Connect MCP servers on startup
        await self.mcp_manager.connect_all()

        while self.running:
            try:
                prompt_text = self._get_prompt()
                user_input = await self.session.prompt_async( # Use async prompt
                    prompt_text,
                    rprompt=self._make_rprompt(),
                )
                
                if user_input is None:
                    continue
                
                user_input = user_input.strip()
                
                if not user_input:
                    continue
                
                if user_input.startswith("/"):
                    if not await self._handle_command(user_input): # await _handle_command
                        break
                    continue
                
                if user_input.startswith("!"):
                    shell_cmd = user_input[1:].strip()
                    if shell_cmd:
                        self.tools.execute_command(shell_cmd) # execute_command is sync
                    continue
                
                await self.agent.process_message(user_input) # await process_message
                
            except KeyboardInterrupt:
                self.console.print("\n[dim]Use /exit to quit[/dim]")
                continue
            except EOFError:
                self.console.print("\n[bold blue]Goodbye![/]")
                break
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/]")
                continue

        await self.mcp_manager.cleanup() # Cleanup MCP connections
        self.context.save()
