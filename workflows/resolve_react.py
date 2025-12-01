import os
import glob
import re
import dspy
from rich.console import Console
from rich.panel import Panel
from agents.workflow.react_todo_resolver import ReActTodoResolver

console = Console()


def _get_ready_todos(pattern: str = None) -> list[dict]:
    """Find all ready todos in the todos directory, optionally filtered by pattern."""
    todos_dir = "todos"
    if not os.path.exists(todos_dir):
        return []

    ready_files = glob.glob(os.path.join(todos_dir, "*-ready-*.md"))

    todos = []
    for file_path in sorted(ready_files):
        filename = os.path.basename(file_path)

        # Filter by pattern if provided
        if pattern and pattern.lower() not in filename.lower():
            continue

        with open(file_path, "r") as f:
            content = f.read()

        # Extract ID from filename
        match = re.match(r"^(\d+)-ready-(.*)\.md$", filename)
        if match:
            todos.append(
                {
                    "id": match.group(1),
                    "slug": match.group(2),
                    "path": file_path,
                    "content": content,
                }
            )
    return todos


def _mark_todo_complete(todo: dict, summary: str) -> None:
    """Mark a todo as complete."""
    new_content = todo["content"].replace("status: ready", "status: complete")

    # Add resolution summary
    resolution_section = f"\n## Resolution Summary\n\n**Status:** ✅ Resolved (ReAct)\n**Summary:** {summary}\n"

    if new_content.startswith("---"):
        parts = new_content.split("---", 2)
        if len(parts) >= 3:
            new_content = f"---{parts[1]}---{resolution_section}{parts[2]}"
    else:
        new_content = resolution_section + new_content

    # Create new filename
    old_path = todo["path"]
    new_filename = os.path.basename(old_path).replace("-ready-", "-complete-")
    new_path = os.path.join(os.path.dirname(old_path), new_filename)

    with open(new_path, "w") as f:
        f.write(new_content)

    if old_path != new_path and os.path.exists(old_path):
        os.remove(old_path)

    console.print(f"[green]✓ Todo {todo['id']} marked complete: {new_path}[/green]")


def run_react_resolve(pattern: str = None, dry_run: bool = False) -> None:
    """
    Resolve todos using ReAct agent.
    """
    console.print(
        Panel.fit(
            "[bold]Compounding Engineering: ReAct Resolve[/bold]\n"
            f"Pattern: {pattern or 'all'} | Dry Run: {dry_run}",
            border_style="magenta",
        )
    )

    todos = _get_ready_todos(pattern)
    if not todos:
        console.print("[yellow]No ready todos found.[/yellow]")
        return

    console.print(f"Found {len(todos)} todos.")

    resolver = dspy.Predict(ReActTodoResolver)

    for todo in todos:
        console.print(
            f"\n[bold cyan]Resolving Todo {todo['id']}: {todo['slug']}[/bold cyan]"
        )

        if dry_run:
            console.print("[yellow]DRY RUN: Would resolve this todo.[/yellow]")
            continue

        try:
            # The ReAct agent will execute tools directly
            result = resolver(todo_content=todo["content"], todo_id=todo["id"])

            if result.success_status:
                console.print(f"[green]Success:[/green] {result.resolution_summary}")
                _mark_todo_complete(todo, result.resolution_summary)
            else:
                console.print(f"[red]Failed:[/red] {result.resolution_summary}")

        except Exception as e:
            console.print(f"[red]Error resolving todo {todo['id']}: {e}[/red]")
