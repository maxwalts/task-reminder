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

    # Try pync first, fall back to osascript
    try:
        import pync
        pync.notify(
            message,
            title=title,
            subtitle=subtitle,
            sound="default"
        )
    except ImportError:
        # Fallback to osascript
        _send_notification_osascript(title, subtitle, message)


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
