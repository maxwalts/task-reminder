"""Read and parse tasks from Apple Notes 'Tasks' folder."""

import subprocess
import re
from dataclasses import dataclass
from html.parser import HTMLParser


@dataclass
class Task:
    """Represents a task from Apple Notes."""
    text: str
    section: str
    note_title: str

    def __hash__(self):
        return hash((self.text, self.note_title))

    def __eq__(self, other):
        if not isinstance(other, Task):
            return False
        return self.text == other.text and self.note_title == other.note_title


APPLESCRIPT_FETCH_NOTES = '''
tell application "Notes"
    set output to ""
    try
        set tasksFolder to folder "Tasks"
        repeat with aNote in notes of tasksFolder
            set noteTitle to name of aNote
            set noteBody to body of aNote
            set output to output & "===NOTE_START===" & noteTitle & "===NOTE_TITLE_END===" & noteBody & "===NOTE_END==="
        end repeat
    on error errMsg
        return "ERROR: " & errMsg
    end try
    return output
end tell
'''


def fetch_notes_content() -> str:
    """Execute AppleScript to fetch all notes from Tasks folder (HTML body)."""
    result = subprocess.run(
        ["osascript", "-e", APPLESCRIPT_FETCH_NOTES],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"AppleScript error: {result.stderr}")
    return result.stdout


class NotesHTMLParser(HTMLParser):
    """Parse Apple Notes HTML to extract tasks with section context."""

    def __init__(self, note_title: str):
        super().__init__()
        self.note_title = note_title
        self.tasks: list[Task] = []
        self.current_section = "general"
        self.in_li = False
        self.in_div = False
        self.in_h1 = False
        self.current_text = ""

    def handle_starttag(self, tag, attrs):
        if tag == "li":
            self.in_li = True
            self.current_text = ""
        elif tag == "div":
            self.in_div = True
            self.current_text = ""
        elif tag == "h1":
            self.in_h1 = True
            self.current_text = ""

    def handle_endtag(self, tag):
        if tag == "li" and self.in_li:
            self.in_li = False
            text = self.current_text.strip()
            # Skip "meta" section (reflections/notes to self, not tasks)
            if text and self.current_section != "meta":
                self.tasks.append(Task(
                    text=text,
                    section=self.current_section,
                    note_title=self.note_title
                ))
            self.current_text = ""

        elif tag == "div" and self.in_div:
            self.in_div = False
            text = self.current_text.strip()
            # Check if this looks like a section header
            # Short text, not starting with special chars
            if (text and
                len(text) < 50 and
                not text.startswith('-') and
                not text.startswith('*')):
                self.current_section = text.lower()
            self.current_text = ""

        elif tag == "h1" and self.in_h1:
            self.in_h1 = False
            # H1 is usually the note title, skip as section
            self.current_text = ""

    def handle_data(self, data):
        if self.in_li or self.in_div or self.in_h1:
            self.current_text += data


def parse_note_content(note_title: str, html_content: str) -> list[Task]:
    """Parse a note's HTML content to extract tasks with section context."""
    parser = NotesHTMLParser(note_title)
    try:
        parser.feed(html_content)
    except Exception:
        pass
    return parser.tasks


def parse_all_notes(raw_content: str) -> list[Task]:
    """Parse the raw AppleScript output into Task objects."""
    if raw_content.startswith("ERROR:"):
        raise RuntimeError(raw_content)

    all_tasks = []

    # Split by note markers
    note_blocks = raw_content.split("===NOTE_START===")

    for block in note_blocks:
        if not block.strip():
            continue

        if "===NOTE_TITLE_END===" not in block:
            continue

        title_end = block.index("===NOTE_TITLE_END===")
        note_title = block[:title_end].strip()

        remaining = block[title_end + len("===NOTE_TITLE_END==="):]

        if "===NOTE_END===" in remaining:
            note_content = remaining[:remaining.index("===NOTE_END===")]
        else:
            note_content = remaining

        tasks = parse_note_content(note_title, note_content)
        all_tasks.extend(tasks)

    return all_tasks


def get_all_tasks() -> list[Task]:
    """Main entry point: fetch and parse all tasks from Apple Notes."""
    try:
        raw_content = fetch_notes_content()
        return parse_all_notes(raw_content)
    except Exception as e:
        print(f"Error fetching tasks: {e}")
        return []
