"""Main entry point for the Task Reminder menu bar app."""

import rumps
import threading
import time
from datetime import datetime

from .notes_reader import get_all_tasks, Task
from .scheduler import (
    get_eligible_tasks,
    categorize_task,
    get_category_display_name,
    CategorizedTask
)
from .state import (
    load_state,
    save_state,
    can_remind_any_task,
    can_remind_task,
    record_reminder,
    cleanup_old_state,
    get_reminder_count
)
from .notifier import send_notification, send_test_notification


# How often to check for tasks and potentially send reminders (seconds)
CHECK_INTERVAL = 600  # 10 minutes


class TaskReminderApp(rumps.App):
    """Menu bar application for task reminders."""

    def __init__(self):
        super().__init__("📋", quit_button=None)

        self.tasks: list[Task] = []
        self.state = load_state()

        # Build initial menu
        self._build_menu()

        # Start background thread for periodic checks
        self._start_background_checker()

    def _build_menu(self):
        """Build the menu bar dropdown menu."""
        self.menu.clear()

        # Header with task count
        task_count = len(self.tasks)
        header = rumps.MenuItem(f"Tasks: {task_count}", callback=None)
        header.set_callback(None)
        self.menu.add(header)

        self.menu.add(rumps.separator)

        # List tasks (up to 10)
        if self.tasks:
            for task in self.tasks[:10]:
                category = categorize_task(task)
                reminder_count = get_reminder_count(task, self.state)

                # Truncate long task text
                display_text = task.text[:40] + "..." if len(task.text) > 40 else task.text

                menu_text = f"{display_text}"
                if task.section and task.section != "general":
                    menu_text += f" [{task.section}]"

                item = rumps.MenuItem(menu_text, callback=None)
                self.menu.add(item)

            if len(self.tasks) > 10:
                self.menu.add(rumps.MenuItem(f"... and {len(self.tasks) - 10} more", callback=None))
        else:
            self.menu.add(rumps.MenuItem("No tasks found", callback=None))

        self.menu.add(rumps.separator)

        # Actions
        self.menu.add(rumps.MenuItem("Refresh Now", callback=self._on_refresh))
        self.menu.add(rumps.MenuItem("Send Test Reminder", callback=self._on_test_reminder))
        self.menu.add(rumps.MenuItem("Trigger Reminder Now", callback=self._on_trigger_reminder))

        self.menu.add(rumps.separator)

        # Status
        if self.state.last_any_reminder:
            try:
                last_time = datetime.fromisoformat(self.state.last_any_reminder)
                time_str = last_time.strftime("%I:%M %p")
                self.menu.add(rumps.MenuItem(f"Last reminder: {time_str}", callback=None))
            except ValueError:
                pass

        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("Quit", callback=self._on_quit))

    def _on_refresh(self, _):
        """Manual refresh callback."""
        self._refresh_tasks()
        rumps.notification(
            "Task Reminder",
            "Refreshed",
            f"Found {len(self.tasks)} tasks"
        )

    def _on_test_reminder(self, _):
        """Send a test notification."""
        send_test_notification()

    def _on_trigger_reminder(self, _):
        """Manually trigger a reminder for an eligible task."""
        eligible = get_eligible_tasks(self.tasks)

        # Filter by individual task cooldown
        eligible = [ct for ct in eligible if can_remind_task(ct.task, self.state)]

        if not eligible:
            rumps.notification(
                "Task Reminder",
                "No eligible tasks",
                "No tasks are available for reminder right now"
            )
            return

        # Pick task with lowest reminder count (fair rotation)
        eligible.sort(key=lambda ct: get_reminder_count(ct.task, self.state))
        selected = eligible[0]

        self._send_reminder(selected)

    def _on_quit(self, _):
        """Quit the application."""
        save_state(self.state)
        rumps.quit_application()

    def _refresh_tasks(self):
        """Fetch tasks from Apple Notes."""
        self.tasks = get_all_tasks()
        self.state = cleanup_old_state(self.state, self.tasks)
        save_state(self.state)
        self._build_menu()

    def _send_reminder(self, categorized_task: CategorizedTask):
        """Send a reminder notification and update state."""
        send_notification(categorized_task.task, categorized_task.category)
        self.state = record_reminder(categorized_task.task, self.state)
        save_state(self.state)
        self._build_menu()

    def _check_and_remind(self):
        """Check if we should send a reminder and do so if appropriate."""
        # Refresh tasks first
        self._refresh_tasks()

        # Check global cooldown
        if not can_remind_any_task(self.state):
            return

        # Get time-appropriate tasks
        eligible = get_eligible_tasks(self.tasks)

        # Filter by individual task cooldown
        eligible = [ct for ct in eligible if can_remind_task(ct.task, self.state)]

        if not eligible:
            return

        # Pick task with lowest reminder count (fair rotation)
        eligible.sort(key=lambda ct: get_reminder_count(ct.task, self.state))
        selected = eligible[0]

        self._send_reminder(selected)

    def _start_background_checker(self):
        """Start background thread that periodically checks for reminders."""
        def checker_loop():
            # Initial refresh
            self._refresh_tasks()

            while True:
                time.sleep(CHECK_INTERVAL)
                try:
                    self._check_and_remind()
                except Exception as e:
                    print(f"Error in background checker: {e}")

        thread = threading.Thread(target=checker_loop, daemon=True)
        thread.start()


def main():
    """Entry point."""
    app = TaskReminderApp()
    app.run()


if __name__ == "__main__":
    main()
