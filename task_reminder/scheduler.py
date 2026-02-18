"""Task categorization and smart scheduling logic."""

from datetime import datetime
from enum import Enum
from dataclasses import dataclass

from .notes_reader import Task


class TaskCategory(Enum):
    """Categories that determine when tasks can be reminded about."""
    BUSINESS_HOURS = "business_hours"  # 9am - 5pm only
    QUICK_ERRAND = "quick_errand"      # Any time
    FOCUS_PROJECT = "focus_project"    # 6pm - 11pm
    SOCIAL_TRIPS = "social_trips"      # Flexible
    SHOPPING = "shopping"              # Any time
    GENERAL = "general"                # Flexible


@dataclass
class CategorizedTask:
    """Task with its determined category."""
    task: Task
    category: TaskCategory


# Keywords for categorization
BUSINESS_KEYWORDS = [
    "call", "schedule", "doctor", "dentist", "appointment",
    "podiatrist", "dermatologist", "therapist", "vet", "clinic",
    "office", "bank", "dmv", "government", "insurance"
]

QUICK_ERRAND_KEYWORDS = [
    "submit", "order", "check", "sign up", "cancel", "renew",
    "update", "confirm", "reply", "respond", "email", "text",
    "send email", "fill out", "complete form"
]

FOCUS_PROJECT_KEYWORDS = [
    "set up", "try", "research", "build", "create", "write",
    "design", "develop", "learn", "study", "read about",
    "remix", "record", "edit", "practice"
]

SOCIAL_TRIP_KEYWORDS = [
    "trip", "tickets", "travel", "vacation", "visit",
    "meet", "dinner", "lunch", "party", "event"
]

SHOPPING_KEYWORDS = [
    "buy", "purchase", "new", "find", "shop", "get",
    "pick up", "amazon", "costco"
]

# Section headers that indicate categories
BUSINESS_SECTIONS = ["health", "medical", "appointments", "admin"]
FOCUS_SECTIONS = ["ai assistant", "music", "projects", "creative", "learning", "research"]
SHOPPING_SECTIONS = ["shopping", "food", "groceries"]


def categorize_task(task: Task) -> TaskCategory:
    """Determine the category of a task based on section and keywords."""
    text_lower = task.text.lower()
    section_lower = task.section.lower()

    # Check section-based categorization first
    if any(s in section_lower for s in BUSINESS_SECTIONS):
        # Health section items that mention calling/scheduling are business hours
        if any(kw in text_lower for kw in BUSINESS_KEYWORDS):
            return TaskCategory.BUSINESS_HOURS

    if any(s in section_lower for s in FOCUS_SECTIONS):
        return TaskCategory.FOCUS_PROJECT

    if any(s in section_lower for s in SHOPPING_SECTIONS):
        # Online shopping is any time
        if any(kw in text_lower for kw in QUICK_ERRAND_KEYWORDS):
            return TaskCategory.QUICK_ERRAND
        return TaskCategory.SHOPPING

    # Keyword-based categorization
    if any(kw in text_lower for kw in BUSINESS_KEYWORDS):
        return TaskCategory.BUSINESS_HOURS

    if any(kw in text_lower for kw in QUICK_ERRAND_KEYWORDS):
        return TaskCategory.QUICK_ERRAND

    if any(kw in text_lower for kw in FOCUS_PROJECT_KEYWORDS):
        return TaskCategory.FOCUS_PROJECT

    if any(kw in text_lower for kw in SOCIAL_TRIP_KEYWORDS):
        return TaskCategory.SOCIAL_TRIPS

    if any(kw in text_lower for kw in SHOPPING_KEYWORDS):
        return TaskCategory.SHOPPING

    # Check for social patterns (sending to specific people)
    if "send" in text_lower and any(word[0].isupper() for word in task.text.split() if len(word) > 0):
        return TaskCategory.SOCIAL_TRIPS

    return TaskCategory.GENERAL


def is_time_appropriate(category: TaskCategory, current_time: datetime = None) -> bool:
    """Check if the current time is appropriate for this task category."""
    if current_time is None:
        current_time = datetime.now()

    hour = current_time.hour

    if category == TaskCategory.BUSINESS_HOURS:
        # 9am - 5pm only
        return 9 <= hour < 17

    elif category == TaskCategory.FOCUS_PROJECT:
        # 6pm - 11pm
        return 18 <= hour < 23

    elif category in (TaskCategory.QUICK_ERRAND, TaskCategory.SHOPPING):
        # Any time (but maybe not too late at night)
        return 7 <= hour < 23

    elif category == TaskCategory.SOCIAL_TRIPS:
        # Flexible, but not too early or late
        return 9 <= hour < 22

    else:  # GENERAL
        # Reasonable hours
        return 8 <= hour < 22


def get_eligible_tasks(tasks: list[Task], current_time: datetime = None) -> list[CategorizedTask]:
    """Filter tasks to only those appropriate for the current time."""
    eligible = []

    for task in tasks:
        category = categorize_task(task)
        if is_time_appropriate(category, current_time):
            eligible.append(CategorizedTask(task=task, category=category))

    return eligible


def get_category_display_name(category: TaskCategory) -> str:
    """Get a human-readable name for the category."""
    names = {
        TaskCategory.BUSINESS_HOURS: "📞 Business Hours",
        TaskCategory.QUICK_ERRAND: "⚡ Quick Task",
        TaskCategory.FOCUS_PROJECT: "🎯 Focus Time",
        TaskCategory.SOCIAL_TRIPS: "👥 Social",
        TaskCategory.SHOPPING: "🛒 Shopping",
        TaskCategory.GENERAL: "📝 General"
    }
    return names.get(category, "📝 Task")
