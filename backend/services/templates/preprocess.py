from __future__ import annotations

import html
import re

_GRID_LINE = re.compile(r"^\+[-+=| ]+\+$")
_PANDOC_RULE = re.compile(r"^[-=]{10,}\s")
_TRAILING_BACKSLASH = re.compile(r"\\$")
_ATX_BOLD_HEADING = re.compile(r"^(#{1,6})\s+\*\*(.+?)\*\*\s*$")
_BOLD_HEADING = re.compile(r"^\*\*(.+?)\*\*\s*$")
_KNOWN_SECTION = re.compile(
    r"^(Meeting Minutes|Previous Action Items|New Action Items(?: Arising)?|"
    r"Action Items|Meeting Time and Location|Decisions|Risks(?: / Issues)?|"
    r"Progress Review|Other Business|Semester Break Progress Review|"
    r"Cluster Hardware(?: & Network Setup)?|Cluster Software Setup Progress)\s*$",
    re.IGNORECASE,
)
_HEADER_FIELD = re.compile(
    r"^(Date/Time|Date|Time|Location|Chairperson|Minute-taker|Participants|Apologies)\s*:",
    re.IGNORECASE,
)


def preprocess_extracted_text(text: str) -> str:
    """Normalize pandoc/docx extraction before LLM conversion."""
    text = normalize_pandoc_html(text)
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        if _GRID_LINE.match(stripped):
            continue
        if stripped.startswith("+") and set(stripped.replace(" ", "")) <= {"+", "-", "|"}:
            continue
        if _PANDOC_RULE.match(stripped) and "|" not in stripped:
            continue

        bold_heading = _ATX_BOLD_HEADING.match(stripped)
        if bold_heading:
            lines.append(f"{bold_heading.group(1)} {bold_heading.group(2)}")
            continue

        lines.append(_TRAILING_BACKSLASH.sub("", line.rstrip()))

    collapsed = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    return collapsed.strip()


def normalize_pandoc_html(text: str) -> str:
    """Convert common pandoc/docx HTML leftovers into plain markdown-ish text."""
    text = html.unescape(text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)

    def strip_tags(value: str) -> str:
        return re.sub(r"<[^>]+>", "", value).strip()

    def list_items(block: str) -> list[str]:
        return [
            strip_tags(item)
            for item in re.findall(r"<li[^>]*>(.*?)</li>", block, flags=re.I | re.S)
            if strip_tags(item)
        ]

    def replace_ul(match: re.Match[str]) -> str:
        return "\n".join(f"- {item}" for item in list_items(match.group(0)))

    def replace_ol(match: re.Match[str]) -> str:
        items = list_items(match.group(0))
        return "\n".join(f"{index}. {item}" for index, item in enumerate(items, start=1))

    text = re.sub(r"<ol[^>]*>.*?</ol>", replace_ol, text, flags=re.I | re.S)
    text = re.sub(r"<ul[^>]*>.*?</ul>", replace_ul, text, flags=re.I | re.S)

    def replace_table(match: re.Match[str]) -> str:
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", match.group(0), flags=re.I | re.S)
        markdown_rows: list[str] = []
        for row in rows:
            cells = re.findall(
                r"<t[hd][^>]*>(.*?)</t[hd]>",
                row,
                flags=re.I | re.S,
            )
            if not cells:
                continue
            cleaned = [strip_tags(cell).replace("|", r"\|") for cell in cells]
            markdown_rows.append("| " + " | ".join(cleaned) + " |")
        if len(markdown_rows) >= 2:
            column_count = markdown_rows[0].count("|") - 1
            separator = "| " + " | ".join(["---"] * column_count) + " |"
            markdown_rows.insert(1, separator)
        return "\n".join(markdown_rows) if markdown_rows else strip_tags(match.group(0))

    text = re.sub(r"<table[^>]*>.*?</table>", replace_table, text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
