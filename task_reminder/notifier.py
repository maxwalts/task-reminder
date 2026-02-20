"""Send macOS notifications."""

import subprocess
from .notes_reader import Task
from .scheduler import TaskCategory, get_category_display_name


def send_notification(task: Task, category: TaskCategory):
    """Send a macOS notification for a task."""
    title = f"Task Reminder"
    subtitle = f"From: {task.note_title}"
    if task.section and task.section != "general":
        subtitle += f" ({task.section})"

    message = task.text
    execute_cmd = _make_open_note_command(task.note_title)

    # Try pync first, fall back to osascript
    try:
        import pync
        pync.notify(
            message,
            title=title,
            subtitle=subtitle,
            sound="default",
            execute=execute_cmd
        )
    except ImportError:
        # Fallback to osascript (no click action support)
        _send_notification_osascript(title, subtitle, message)


def _make_open_note_command(note_title: str) -> str:
    """Create a shell command to open a specific note in Apple Notes when clicked."""
    # Escape double quotes for AppleScript string literal
    as_title = note_title.replace('"', '\\"')
    # Escape single quotes for shell single-quoted string using the '\'' trick
    shell_title = as_title.replace("'", "'\\''")
    return (
        f"osascript "
        f"-e 'tell application \"Notes\" to activate' "
        f"-e 'tell application \"Notes\" to show folder \"Tasks\"' "
        f"-e 'tell application \"Notes\" to show "
        f"(first note of folder \"Tasks\" whose name is \"{shell_title}\")'"
    )


def _send_notification_osascript(title: str, subtitle: str, message: str):
    """Send notification using osascript as fallback."""
    script = f'''
    display notification "{message}" with title "{title}" subtitle "{subtitle}" sound name "default"
    '''
    subprocess.run(["osascript", "-e", script], capture_output=True)


def send_test_notification():
    """Send a test notification to verify the system works."""
    script = '''
    display notification "Task Reminder is running!" with title "Task Reminder" subtitle "Test notification" sound name "default"
    '''
    subprocess.run(["osascript", "-e", script], capture_output=True)
