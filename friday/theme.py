"""Friday Theme - Visual styling for the CLI"""

from rich.theme import Theme
from prompt_toolkit.styles import Style as PTStyle

# Theme profiles: dark (default), light, high-contrast (hc)
THEMES = {
    "dark": Theme({
        "info": "cyan",
        "warning": "yellow",
        "error": "red bold",
        "success": "green",
        "user": "bold cyan",
        "assistant": "bold green",
        "tool": "bold yellow",
        "tool.name": "yellow",
        "tool.output": "dim",
        "code": "white on grey23",
        "path": "cyan underline",
        "command": "bold magenta",
        "thinking": "dim italic",
        "highlight": "bold white",
    }),
    "light": Theme({
        "info": "blue",
        "warning": "dark_orange",
        "error": "red bold",
        "success": "green",
        "user": "bold blue",
        "assistant": "bold green4",
        "tool": "bold dark_orange",
        "tool.name": "dark_orange",
        "tool.output": "grey46",
        "code": "black on white",
        "path": "blue underline",
        "command": "bold magenta",
        "thinking": "grey54 italic",
        "highlight": "bold black",
    }),
    "hc": Theme({
        "info": "bright_cyan",
        "warning": "bright_yellow",
        "error": "bright_red bold",
        "success": "bright_green",
        "user": "bold bright_cyan",
        "assistant": "bold bright_green",
        "tool": "bold bright_yellow",
        "tool.name": "bright_yellow",
        "tool.output": "white",
        "code": "black on bright_white",
        "path": "bright_cyan underline",
        "command": "bold bright_magenta",
        "thinking": "bright_white italic",
        "highlight": "bold bright_white",
    }),
}

# Backwards compatibility default theme name
FRIDAY_THEME = THEMES["dark"]

def get_rich_theme(profile: str | None) -> Theme:
    return THEMES.get((profile or "dark").lower(), THEMES["dark"])

def get_prompt_style(profile: str | None = None) -> PTStyle:
    """Get prompt_toolkit style for input for a given theme profile"""
    p = (profile or "dark").lower()
    if p == "light":
        return PTStyle.from_dict({
            '': '#000000',
            'prompt': '#0066cc bold',
            'prompt.path': '#0066cc',
            'prompt.arrow': '#008000 bold',
            'completion-menu.completion': 'bg:#e6e6e6 #000000',
            'completion-menu.completion.current': 'bg:#99ccff #000000',
            'scrollbar.background': 'bg:#e6e6e6',
            'scrollbar.button': 'bg:#b3b3b3',
        })
    if p == "hc":
        return PTStyle.from_dict({
            '': '#ffffff',
            'prompt': 'bold #00ffff',
            'prompt.path': '#00ffff',
            'prompt.arrow': 'bold #00ff00',
            'completion-menu.completion': 'bg:#000000 #ffffff',
            'completion-menu.completion.current': 'bg:#00ffff #000000',
            'scrollbar.background': 'bg:#000000',
            'scrollbar.button': 'bg:#888888',
        })
    # dark default
    return PTStyle.from_dict({
        '': '#ffffff',
        'prompt': '#00aaff bold',
        'prompt.path': '#00aaff',
        'prompt.arrow': '#00ff00 bold',
        'completion-menu.completion': 'bg:#333333 #ffffff',
        'completion-menu.completion.current': 'bg:#00aaff #000000',
        'scrollbar.background': 'bg:#333333',
        'scrollbar.button': 'bg:#666666',
    })


SPINNER_STYLES = [
    "dots",
    "dots2", 
    "dots3",
    "line",
    "arc",
    "bouncingBar",
]

ASCII_ART = {
    "friday": r"""
  _____ ____  ___ ____    _ __   __
 |  ___|  _ \|_ _|  _ \  / \\ \ / /
 | |_  | |_) || || | | |/ _ \\ V / 
 |  _| |  _ < | || |_| / ___ \| |  
 |_|   |_| \_\___|____/_/   \_\_|  
""",
    "thinking": "🤔",
    "success": "✓",
    "error": "✗",
    "warning": "⚠",
    "info": "ℹ",
    "tool": "🔧",
    "file": "📄",
    "folder": "📁",
    "git": "🔀",
    "search": "🔍",
    "edit": "✏️",
    "run": "▶",
}

FILE_ICONS = {
    ".py": "🐍",
    ".js": "📜",
    ".ts": "📘",
    ".tsx": "⚛️",
    ".jsx": "⚛️",
    ".json": "📋",
    ".yaml": "📋",
    ".yml": "📋",
    ".md": "📝",
    ".txt": "📄",
    ".sh": "🔧",
    ".bash": "🔧",
    ".zsh": "🔧",
    ".css": "🎨",
    ".html": "🌐",
    ".sql": "🗃️",
    ".rs": "🦀",
    ".go": "🐹",
    ".rb": "💎",
    ".java": "☕",
    ".c": "⚙️",
    ".cpp": "⚙️",
    ".h": "⚙️",
}

def get_file_icon(filename: str) -> str:
    """Get icon for a file based on extension"""
    ext = "." + filename.split(".")[-1] if "." in filename else ""
    return FILE_ICONS.get(ext, "📄")
