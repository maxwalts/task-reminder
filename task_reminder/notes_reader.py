"""Read and parse tasks from Apple Notes 'Tasks' folder via SQLite + protobuf."""

import json
import os
import sqlite3
import zlib
from dataclasses import dataclass

try:
    import blackboxprotobuf
    BLACKBOXPROTOBUF_AVAILABLE = True
except ImportError:
    BLACKBOXPROTOBUF_AVAILABLE = False

DB_PATH = os.path.expanduser(
    "~/Library/Group Containers/group.com.apple.notes/NoteStore.sqlite"
)

# Set DEBUG_NOTES=1 to print decoded protobuf structure for one note,
# which helps identify correct field numbers if tasks don't parse correctly.
DEBUG = os.environ.get("DEBUG_NOTES", "").strip() not in ("", "0")

# Apple Notes paragraph types (from reverse engineering of NoteStore.sqlite protobuf).
# If tasks aren't appearing, check DEBUG output and update these.
_CHECKLIST_PARA_TYPE = 103  # checklist item (can be checked/unchecked)
_LIST_PARA_TYPES = {4, 5, 6}  # dotted, dashed, numbered list — always active


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


def _make_printable(obj, depth=0):
    """Recursively convert a protobuf-decoded object to something JSON-printable."""
    if depth > 5:
        return "..."
    if isinstance(obj, bytes):
        try:
            return obj.decode("utf-8")
        except Exception:
            return f"<bytes:{len(obj)}>"
    if isinstance(obj, dict):
        return {k: _make_printable(v, depth + 1) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_printable(v, depth + 1) for v in obj[:10]]
    return obj


def _to_int(val, default: int = 0) -> int:
    """Convert a protobuf value (bytes or int) to int."""
    if val is None:
        return default
    if isinstance(val, bytes):
        return int.from_bytes(val, "little") if val else default
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _decode_note_data(zdata: bytes) -> dict:
    """Decompress zlib/gzip and decode protobuf note data."""
    raw = zlib.decompress(zdata, zlib.MAX_WBITS | 32)  # auto-detect zlib or gzip
    message, _ = blackboxprotobuf.decode_message(raw)
    return message


def _find_note_document(message: dict) -> dict | None:
    """Navigate the top-level protobuf wrapper to find the note document dict.

    Apple Notes wraps the note content in one or two levels of container
    messages. We look for the innermost dict that has field '2' (text) and
    field '5' (attribute runs). Field layout observed in macOS Sequoia:
      message["2"]["3"] = note document (text at ["2"], runs at ["5"])
    """
    candidate = message.get("2")
    if not isinstance(candidate, dict):
        return None

    # Newer Notes format: note doc is at message["2"]["3"]
    inner3 = candidate.get("3")
    if isinstance(inner3, dict) and ("2" in inner3 or "5" in inner3):
        return inner3

    # Older format: message["2"]["2"]
    inner2 = candidate.get("2")
    if isinstance(inner2, dict) and ("2" in inner2 or "5" in inner2):
        return inner2

    if "2" in candidate or "5" in candidate:
        return candidate

    return None


def _extract_tasks_from_note(note_title: str, message: dict) -> list[Task]:
    """Extract unchecked tasks from a decoded protobuf note message.

    Attribute run layout (macOS Sequoia / newer Notes):
      run["1"]       = character length (int)
      run["2"]       = attribute dict
      run["2"]["1"]  = paragraphType enum (103 = checklist item)
      run["2"]["5"]  = checklist sub-message {"2": 0|1} where "2" = isDone
    Multiple consecutive runs can make up a single paragraph; we accumulate
    until we hit a newline before emitting a task.
    """
    tasks: list[Task] = []

    if DEBUG:
        print(f"\n=== DEBUG: Note '{note_title}' ===")
        print(json.dumps(_make_printable(message), indent=2, default=str))

    doc = _find_note_document(message)
    if doc is None:
        if DEBUG:
            print(f"  [DEBUG] Could not find note document; top-level keys: {list(message.keys())}")
        return tasks

    # Field '2' holds the flat UTF-8 text of the entire note.
    note_text = doc.get("2", "")
    if isinstance(note_text, bytes):
        note_text = note_text.decode("utf-8", errors="replace")
    if not isinstance(note_text, str) or not note_text:
        if DEBUG:
            print(f"  [DEBUG] No note text at doc['2']; doc keys: {list(doc.keys())}")
        return tasks

    if DEBUG:
        print(f"  [DEBUG] Note text snippet: {repr(note_text[:200])}")

    # Field '5' holds repeated AttributeRun entries (sequential, non-overlapping).
    attr_runs = doc.get("5", [])
    if not isinstance(attr_runs, list):
        attr_runs = [attr_runs]

    if DEBUG:
        print(f"  [DEBUG] Attribute run count: {len(attr_runs)}")

    current_section = "general"
    text_pos = 0

    # Accumulate text/metadata across runs until we hit a paragraph boundary (\n).
    pending_text = ""
    pending_type: int | None = None
    pending_done = False

    def flush_paragraph() -> None:
        nonlocal current_section, pending_text, pending_type, pending_done
        clean_text = pending_text.strip()
        effective_type = pending_type if pending_type is not None else 0

        if clean_text:
            if effective_type == _CHECKLIST_PARA_TYPE:
                if DEBUG:
                    print(f"  [DEBUG] Checklist para: is_done={pending_done}, text={repr(clean_text[:60])}")
                if not pending_done and current_section != "meta":
                    tasks.append(Task(text=clean_text, section=current_section, note_title=note_title))
            elif effective_type in _LIST_PARA_TYPES:
                if current_section != "meta":
                    tasks.append(Task(text=clean_text, section=current_section, note_title=note_title))
            else:
                # Plain text — treat as section header if short enough.
                if len(clean_text) < 50 and not clean_text.startswith(("-", "*", "•")):
                    current_section = clean_text.lower()

        pending_text = ""
        pending_type = None
        pending_done = False

    for i, run in enumerate(attr_runs):
        if not isinstance(run, dict):
            continue

        run_length = _to_int(run.get("1", 1))
        run_text = note_text[text_pos:text_pos + run_length]
        text_pos += run_length

        # Attribute dict lives at run["2"].
        attrs = run.get("2", {})
        if not isinstance(attrs, dict):
            attrs = {}

        # Update paragraph type if this run carries one.
        if "1" in attrs:
            pending_type = _to_int(attrs["1"])

        # Update isDone from checklist sub-message at attrs["5"]["2"].
        checklist = attrs.get("5", {})
        if isinstance(checklist, dict) and "2" in checklist:
            pending_done = bool(_to_int(checklist.get("2", 0)))

        if DEBUG and run_text.strip():
            print(
                f"  [DEBUG] Run {i}: length={run_length}, para_type={pending_type}, "
                f"attr_keys={list(attrs.keys())}, text={repr(run_text[:60])}"
            )

        # Split on \n to handle runs that span multiple paragraphs.
        while "\n" in run_text:
            idx = run_text.index("\n")
            pending_text += run_text[:idx]
            flush_paragraph()
            run_text = run_text[idx + 1:]

        pending_text += run_text

    # Flush any trailing paragraph without a terminating newline.
    if pending_text.strip():
        flush_paragraph()

    return tasks


def _fetch_tasks_from_db() -> list[Task]:
    """Connect to the Notes SQLite database and extract tasks from the Tasks folder."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        cur = conn.cursor()

        cur.execute("SELECT Z_ENT FROM Z_PRIMARYKEY WHERE Z_NAME = 'ICFolder'")
        row = cur.fetchone()
        if not row:
            raise RuntimeError("ICFolder entity type not found in Z_PRIMARYKEY")
        folder_ent = row[0]

        cur.execute("SELECT Z_ENT FROM Z_PRIMARYKEY WHERE Z_NAME = 'ICNote'")
        row = cur.fetchone()
        if not row:
            raise RuntimeError("ICNote entity type not found in Z_PRIMARYKEY")
        note_ent = row[0]

        cur.execute(
            """
            SELECT o.ZTITLE1, d.ZDATA
            FROM ZICCLOUDSYNCINGOBJECT o
            JOIN ZICNOTEDATA d ON d.Z_PK = o.ZNOTEDATA
            WHERE o.ZFOLDER = (
                SELECT Z_PK FROM ZICCLOUDSYNCINGOBJECT
                WHERE ZTITLE2 = 'Tasks'
                  AND Z_ENT = ?
            )
            AND o.Z_ENT = ?
            AND (o.ZMARKEDFORDELETION = 0 OR o.ZMARKEDFORDELETION IS NULL)
            """,
            (folder_ent, note_ent),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    all_tasks: list[Task] = []
    debug_limit = 1  # Only dump full protobuf for first note in DEBUG mode

    for note_title, zdata in rows:
        if not zdata:
            continue
        try:
            message = _decode_note_data(bytes(zdata))
            tasks = _extract_tasks_from_note(note_title, message)
            all_tasks.extend(tasks)
        except Exception as e:
            print(f"Error parsing note '{note_title}': {e}")
            if DEBUG:
                import traceback
                traceback.print_exc()

    return all_tasks


def get_all_tasks() -> list[Task]:
    """Main entry point: fetch and parse all tasks from Apple Notes."""
    if not BLACKBOXPROTOBUF_AVAILABLE:
        print("Error: blackboxprotobuf is not installed. Run: pip install blackboxprotobuf")
        return []

    try:
        return _fetch_tasks_from_db()
    except Exception as e:
        msg = str(e).lower()
        print(f"Error fetching tasks from Notes database: {e}")
        if any(x in msg for x in ("unable to open", "permission", "denied", "read-only")):
            print(
                "  → Grant Full Disk Access to Terminal in "
                "System Settings → Privacy & Security → Full Disk Access"
            )
        return []
