import dspy
from utils.file_tools import (
    list_directory,
    search_files,
    read_file_range,
    edit_file_lines,
)


class TodoResolutionSignature(dspy.Signature):
    """You are a file editing specialist using ReAct reasoning.

    Analyze the todo and make necessary file changes through iterative
    reasoning: think about what needs to change, use tools to examine
    and modify files, observe results, and iterate until the todo is resolved.

    You have access to the following tools:
    - list_directory(path): List files and directories.
    - search_files(query, path, regex): Search for string/regex in files.
    - read_file_range(file_path, start_line, end_line): Read specific lines.
    - edit_file_lines(file_path, edits): Edit specific lines. 'edits' is a list of dicts with 'start_line', 'end_line', 'content'.
    """

    todo_content = dspy.InputField(desc="Content of the todo file")
    todo_id = dspy.InputField(desc="Unique identifier of the todo")

    resolution_summary = dspy.OutputField(desc="What was accomplished")
    files_modified = dspy.OutputField(desc="List of files that were changed")
    reasoning_trace = dspy.OutputField(desc="Step-by-step ReAct reasoning process")
    success_status = dspy.OutputField(desc="Whether resolution was successful")


class ReActTodoResolver(dspy.Module):
    def __init__(self):
        super().__init__()

        # Define tools
        self.tools = [list_directory, search_files, read_file_range, edit_file_lines]

        # Create ReAct agent
        self.react_agent = dspy.ReAct(
            signature=TodoResolutionSignature, tools=self.tools, max_iters=15
        )

    def forward(self, todo_content: str, todo_id: str):
        """Resolve todo using ReAct reasoning."""
        return self.react_agent(todo_content=todo_content, todo_id=todo_id)
