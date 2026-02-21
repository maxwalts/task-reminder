# Task Reminder

A macOS menu bar app that reads your tasks from Apple Notes and periodically nudges you about them via system notifications.

## How it works

- Reads tasks from a **"Tasks" folder** in Apple Notes by querying the Notes SQLite database directly
- Correctly excludes checked-off checklist items (something AppleScript cannot do)
- Categorizes tasks by time-of-day appropriateness (business hours, evening focus time, anytime, etc.)
- Sends a macOS notification for an eligible task every 10 minutes, rotating fairly across tasks
- Lives in the menu bar — shows your current task list and lets you trigger reminders manually

## Requirements

- macOS (tested on macOS 13+)
- Python 3.10+
- An **Apple Notes folder named "Tasks"** containing notes with list items
- **Full Disk Access** granted to Terminal (or your Python binary) — required to read the Notes database

### Apple Notes setup

Create a folder called **Tasks** in Apple Notes. Each note can contain:
- Bullet/numbered list items — these become individual tasks
- Section headers (short `div` text) to categorize tasks (e.g. "Health", "Shopping", "Projects")
- A `meta` section for notes-to-self that should not trigger reminders

## Installation

```bash
git clone https://github.com/your-username/task-reminder.git
cd task-reminder
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Grant **Full Disk Access** to Terminal in **System Settings → Privacy & Security → Full Disk Access**. This is required so the app can read the Notes SQLite database. Without it, no tasks will be shown.

## Usage

### Starting the app

```bash
cd task-reminder
source .venv/bin/activate
task-reminder &
```

The app appears as 📋 in your menu bar. Click it to:
- See your current task list
- Manually refresh tasks from Notes
- Send a test notification
- Trigger a reminder immediately
- Quit

### Killing the app

Click **Quit** in the menu bar popup, or run:

```bash
pkill -f task_reminder
```

## Task categorization

Tasks are categorized by section name and keywords, which controls when reminders fire:

| Category | Active hours | Triggered by |
|---|---|---|
| Business Hours | 9am–5pm | "call", "appointment", "doctor", etc. |
| Quick Errand | 7am–11pm | "submit", "email", "check", etc. |
| Focus Project | 6pm–11pm | "research", "build", "write", etc. |
| Social/Trips | 9am–10pm | "trip", "dinner", "meet", etc. |
| Shopping | 7am–11pm | "buy", "order", "amazon", etc. |
| General | 8am–10pm | everything else |

## Reminder behavior

- Minimum 45 minutes between any two reminders
- Each individual task has a 4-hour cooldown before it can be reminded again
- Tasks are rotated fairly (least-reminded task goes first)
- State is saved to `~/.task_reminder_state.json`

## License

MIT
