"""Persist reminder state to avoid re-reminding."""

import json
import os
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

from .notes_reader import Task


STATE_FILE = Path.home() / ".task_reminder_state.json"

# Don't re-remind about the same task for this many hours
REMINDER_COOLDOWN_HOURS = 4

# Minimum minutes between any reminders
MIN_REMINDER_SPACING_MINUTES = 45


@dataclass
class TaskReminderState:
    """State for a single task's reminder history."""
    task_text: str
    note_title: str
    last_reminded: str  # ISO format datetime
    reminder_count: int


@dataclass
class AppState:
    """Overall application state."""
    task_states: dict[str, TaskReminderState]  # key is task_text:note_title
    last_any_reminder: Optional[str]  # ISO format datetime

    def to_dict(self) -> dict:
        return {
            "task_states": {k: asdict(v) for k, v in self.task_states.items()},
            "last_any_reminder": self.last_any_reminder
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AppState":
        task_states = {}
        for k, v in data.get("task_states", {}).items():
            task_states[k] = TaskReminderState(**v)
        return cls(
            task_states=task_states,
            last_any_reminder=data.get("last_any_reminder")
        )


def _task_key(task: Task) -> str:
    """Generate a unique key for a task."""
    return f"{task.text}:{task.note_title}"


def load_state() -> AppState:
    """Load state from disk."""
    if not STATE_FILE.exists():
        return AppState(task_states={}, last_any_reminder=None)

    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
            return AppState.from_dict(data)
    except (json.JSONDecodeError, KeyError, TypeError):
        return AppState(task_states={}, last_any_reminder=None)


def save_state(state: AppState):
    """Save state to disk."""
    with open(STATE_FILE, "w") as f:
        json.dump(state.to_dict(), f, indent=2)


def can_remind_any_task(state: AppState) -> bool:
    """Check if enough time has passed since the last reminder."""
    if state.last_any_reminder is None:
        return True

    last_time = datetime.fromisoformat(state.last_any_reminder)
    elapsed = datetime.now() - last_time
    return elapsed.total_seconds() >= MIN_REMINDER_SPACING_MINUTES * 60


def can_remind_task(task: Task, state: AppState) -> bool:
    """Check if we can remind about this specific task."""
    key = _task_key(task)

    if key not in state.task_states:
        return True

    task_state = state.task_states[key]
    last_time = datetime.fromisoformat(task_state.last_reminded)
    elapsed = datetime.now() - last_time
    return elapsed.total_seconds() >= REMINDER_COOLDOWN_HOURS * 3600


def record_reminder(task: Task, state: AppState) -> AppState:
    """Record that we reminded about a task."""
    key = _task_key(task)
    now_iso = datetime.now().isoformat()

    if key in state.task_states:
        task_state = state.task_states[key]
        task_state.last_reminded = now_iso
        task_state.reminder_count += 1
    else:
        state.task_states[key] = TaskReminderState(
            task_text=task.text,
            note_title=task.note_title,
            last_reminded=now_iso,
            reminder_count=1
        )

    state.last_any_reminder = now_iso
    return state


def get_reminder_count(task: Task, state: AppState) -> int:
    """Get how many times we've reminded about this task."""
    key = _task_key(task)
    if key in state.task_states:
        return state.task_states[key].reminder_count
    return 0


def cleanup_old_state(state: AppState, current_tasks: list[Task]) -> AppState:
    """Remove state for tasks that no longer exist (were checked off)."""
    current_keys = {_task_key(t) for t in current_tasks}
    state.task_states = {
        k: v for k, v in state.task_states.items()
        if k in current_keys
    }
    return state
