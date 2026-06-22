from __future__ import annotations

import re

from backend.services.templates.prompts import BATCH_END_MARKER

_GRID_LINE = re.compile(r"^\+[-+=| ]+\+$")
_PANDOC_RULE = re.compile(r"^[-=]{10,}\s")
_DOCUMENT_TAG = re.compile(r"</?document>", re.IGNORECASE)
_BLANK_PLACEHOLDER = re.compile(r"\[blank row\]|\[sub blank row\]", re.IGNORECASE)
_BROKEN_ROW = re.compile(r"\|\s*\]")
_TRAILING_BACKSLASH = re.compile(r"\\$")


_HEADER_FIELD = re.compile(
    r"^(Date/Time|Date|Time|Location|Chairperson|Minute-taker|Participants|Apologies)\s*:",
    re.IGNORECASE,
)
_BOLD_HEADING = re.compile(r"^\*\*(.+?)\*\*\s*$")


def strip_batch_markers(content: str) -> str:
    lines = [
        line
        for line in content.splitlines()
        if line.strip() != BATCH_END_MARKER
    ]
    collapsed = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    return collapsed.strip()


def ensure_batch_end_marker(content: str) -> str:
    cleaned = strip_batch_markers(content)
    if not cleaned:
        return cleaned
    return f"{cleaned}\n\n{BATCH_END_MARKER}"


def strip_document_header(content: str) -> str:
    """Remove the top metadata block from chunk output when merging."""
    lines = content.splitlines()
    output: list[str] = []
    past_header = False

    for line in lines:
        stripped = line.strip()
        if not past_header:
            if _HEADER_FIELD.match(stripped):
                continue
            if stripped.startswith("## ") or _BOLD_HEADING.match(stripped):
                past_header = True
            elif stripped and not stripped.startswith("|"):
                continue
            else:
                past_header = True

        output.append(line)

    return "\n".join(output).strip() or content.strip()


def sanitize_template_draft(content: str) -> str:
    lines = content.splitlines()
    output: list[str] = []
    seen_h2: set[str] = set()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            output.append("")
            continue
        if _DOCUMENT_TAG.search(stripped):
            continue
        if stripped == BATCH_END_MARKER:
            continue
        if _GRID_LINE.match(stripped):
            continue
        if stripped.startswith("+") and set(stripped.replace(" ", "")) <= {"+", "-", "|"}:
            continue
        if _PANDOC_RULE.match(stripped) and "|" not in stripped:
            continue
        if _BLANK_PLACEHOLDER.search(stripped):
            continue
        if _BROKEN_ROW.search(stripped) and stripped.count("|") >= 3:
            continue

        heading = re.match(r"^#{2}\s+\*{0,2}(.+?)\*{0,2}\s*$", stripped)
        if heading:
            key = heading.group(1).strip().lower()
            if key in seen_h2:
                continue
            seen_h2.add(key)

        output.append(_TRAILING_BACKSLASH.sub("", line.rstrip()))

    collapsed = re.sub(r"\n{3,}", "\n\n", "\n".join(output))
    return collapsed.strip()
