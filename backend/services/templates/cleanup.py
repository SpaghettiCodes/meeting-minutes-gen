from __future__ import annotations

import re

from backend.services.templates.prompts import BATCH_END_MARKER


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
