import dspy
import functools

from utils.file_tools import (
    create_file,
    edit_file_lines,
    list_directory,
    read_file_range,
    search_files,
)


class TodoResolutionSignature(dspy.Signature):
    """You are a file editing specialist using ReAct reasoning.

    Analyze the todo and make necessary file changes through iterative
    reasoning: think about what needs to change, use tools to examine
    and modify files, observe results, and iterate until the todo is resolved.

    CRITICAL VERIFICATION REQUIREMENTS:

    1. AFTER completing all edits, you MUST read back the changed sections
       of ALL modified files to ensure the changes were applied correctly.

    2. FOR STRUCTURED FILES, you MUST validate syntax:
       - TOML files (.toml): Verify brackets, quotes, and structure are valid
       - YAML files (.yaml, .yml): Verify indentation and structure
       - JSON files (.json): Verify brackets, braces, quotes, commas
       - Python files (.py): Verify no syntax errors (missing colons, brackets, etc.)

    3. If you detect any syntax errors during verification:
       - Re-edit the file to fix the error
       - Re-verify until the file is valid
       - Do NOT mark the task complete with syntax errors

    Do not assume success without these verification steps. Syntax errors in
    configuration files (like pyproject.toml) can break the entire system.

    You have access to the following tools:
    - list_directory(path): List files and directories.
    - search_files(query, path, regex): Search for string/regex in files.
    - read_file_range(file_path, start_line, end_line): Read specific lines.
    - edit_file_lines(file_path, edits): Edit specific lines. 'edits' is a list of dicts with 'start_line', 'end_line', 'content'.
    - create_file(file_path, content): Create a new file with content.

    CRITICAL: When using edit_file_lines, the 'content' MUST NOT include the surrounding lines (context) unless you INTEND to duplicate them.
    - If you want to replace line 10, 'edits' should be [{'start_line': 10, 'end_line': 10, 'content': 'new_line_10_content'}].
    - DO NOT include lines 9 or 11 in 'content' unless you are changing them too.
    - TRIPLE QUOTES (''') HAZARD: When editing docstrings or multiline strings, be careful not to break the tool call syntax.
    """

    todo_content: str = dspy.InputField(desc="Content of the todo file")
    todo_id: str = dspy.InputField(desc="Unique identifier of the todo")

    resolution_summary: str = dspy.OutputField(desc="What was accomplished")
    files_modified: list[str] = dspy.OutputField(desc="List of files that were changed")
    reasoning_trace: str = dspy.OutputField(desc="Step-by-step ReAct reasoning process")
    verification_status: dict[str, str] = dspy.OutputField(
        desc="Verification results for each modified file. Key=filename, Value=status (verified/FAILED)"
    )
    success_status: bool = dspy.OutputField(desc="Whether resolution was successful")


class ReActTodoResolver(dspy.Module):
    def __init__(self, base_dir: str = "."):
        super().__init__()

        # Define tools with base_dir bound
        from functools import partial

        self.tools = [
            partial(list_directory, base_dir=base_dir),
            partial(search_files, base_dir=base_dir),
            partial(read_file_range, base_dir=base_dir),
            partial(edit_file_lines, base_dir=base_dir),
            partial(create_file, base_dir=base_dir),
        ]

        # Update tool names and docstrings to match originals (needed for dspy)
        # Update tool names and docstrings to match originals (needed for dspy)
        from rich.console import Console

        console = Console()

        def make_logged_tool(tool_func):
            # functools.wraps fails on partials, so we manually wrap
            def wrapper(*args, **kwargs):
                # Format args for display
                args_str = ", ".join([str(a) for a in args])
                kwargs_str = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
                all_args = ", ".join(filter(None, [args_str, kwargs_str]))

                # Truncate long args
                if len(all_args) > 100:
                    all_args = all_args[:97] + "..."

                console.print(
                    f"[dim]  → ReAct Tool: {tool_func.__name__ if hasattr(tool_func, '__name__') else 'partial'}({all_args})[/dim]"
                )
                return tool_func(*args, **kwargs)

            # Manually copy metadata from the real function
            real_func = tool_func
            while isinstance(real_func, functools.partial):
                real_func = real_func.func

            wrapper.__name__ = real_func.__name__
            wrapper.__doc__ = real_func.__doc__

            return wrapper

        self.tools = [
            make_logged_tool(partial(list_directory, base_dir=base_dir)),
            make_logged_tool(partial(search_files, base_dir=base_dir)),
            make_logged_tool(partial(read_file_range, base_dir=base_dir)),
            make_logged_tool(partial(edit_file_lines, base_dir=base_dir)),
            make_logged_tool(partial(create_file, base_dir=base_dir)),
        ]

        # Create ReAct agent
        self.react_agent = dspy.ReAct(
            signature=TodoResolutionSignature, tools=self.tools, max_iters=15
        )

    def forward(self, todo_content: str, todo_id: str):
        """Resolve todo using ReAct reasoning."""
        return self.react_agent(todo_content=todo_content, todo_id=todo_id)
