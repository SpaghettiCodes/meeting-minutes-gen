from __future__ import annotations

import re
from dataclasses import dataclass

_ATX_HEADING = re.compile(r"^(#{1,3})\s+(.+)$")
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


@dataclass(frozen=True)
class DocumentSection:
    heading: str | None
    body: str


@dataclass(frozen=True)
class StructuredChunk:
    content: str
    section_titles: list[str]
    includes_document_header: bool


def split_document_text(
    text: str,
    *,
    max_chunk_chars: int,
    page_texts: list[str] | None = None,
) -> list[str]:
    return [
        chunk.content
        for chunk in split_document_structured(
            text,
            max_chunk_chars=max_chunk_chars,
            page_texts=page_texts,
        )
    ]


def split_document_structured(
    text: str,
    *,
    max_chunk_chars: int,
    page_texts: list[str] | None = None,
) -> list[StructuredChunk]:
    if max_chunk_chars <= 0:
        raise ValueError("max_chunk_chars must be positive.")

    text = text.strip()
    if not text:
        return []

    if len(text) <= max_chunk_chars:
        return [
            StructuredChunk(
                content=text,
                section_titles=_section_titles_from_text(text),
                includes_document_header=_has_document_header(text),
            )
        ]

    sections = split_into_sections(text)
    if len(sections) > 1:
        packed = _pack_sections(sections, max_chunk_chars=max_chunk_chars)
        if packed:
            return packed

    if page_texts:
        chunks = _chunk_by_units(page_texts, max_chunk_chars, joiner="\n\n")
        if chunks:
            return _wrap_plain_chunks(chunks)

    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    if len(paragraphs) > 1:
        chunks = _chunk_by_units(paragraphs, max_chunk_chars, joiner="\n\n")
        if chunks:
            return _wrap_plain_chunks(chunks)

    return _wrap_plain_chunks(_chunk_by_lines(text, max_chunk_chars))


def split_into_sections(text: str) -> list[DocumentSection]:
    lines = text.splitlines()
    if not lines:
        return []

    sections: list[DocumentSection] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_heading, current_lines
        if not current_lines and current_heading is None:
            return
        body = "\n".join(current_lines).strip()
        if body or current_heading is not None:
            sections.append(DocumentSection(heading=current_heading, body=body))
        current_heading = None
        current_lines = []

    for line in lines:
        heading = _detect_section_heading(line.strip())
        if heading is not None:
            flush()
            current_heading = heading
            current_lines = [f"## {heading}"]
            continue
        current_lines.append(line)

    flush()
    return [section for section in sections if section.body.strip()]


def _detect_section_heading(line: str) -> str | None:
    if not line:
        return None

    atx = _ATX_HEADING.match(line)
    if atx:
        return _clean_heading_text(atx.group(2))

    bold = _BOLD_HEADING.match(line)
    if bold:
        return _clean_heading_text(bold.group(1))

    known = _KNOWN_SECTION.match(line)
    if known:
        return _clean_heading_text(known.group(1))

    return None


def _clean_heading_text(value: str) -> str:
    return re.sub(r"\*+", "", value).strip()


def _pack_sections(
    sections: list[DocumentSection],
    *,
    max_chunk_chars: int,
) -> list[StructuredChunk]:
    chunks: list[StructuredChunk] = []
    current_sections: list[DocumentSection] = []
    current_len = 0

    def flush_current() -> None:
        nonlocal current_sections, current_len
        if not current_sections:
            return
        chunks.append(
            _sections_to_chunk(
                current_sections,
                includes_document_header=not chunks,
            )
        )
        current_sections = []
        current_len = 0

    for section in sections:
        section_text = _format_section(section)
        if len(section_text) > max_chunk_chars:
            flush_current()
            chunks.extend(
                _split_oversized_section(
                    section,
                    max_chunk_chars=max_chunk_chars,
                    includes_document_header=not chunks,
                )
            )
            continue

        added_len = len(section_text) if not current_sections else len(section_text) + 2
        if current_sections and current_len + added_len > max_chunk_chars:
            flush_current()

        current_sections.append(section)
        current_len += added_len

    flush_current()
    return chunks


def _split_oversized_section(
    section: DocumentSection,
    *,
    max_chunk_chars: int,
    includes_document_header: bool,
) -> list[StructuredChunk]:
    heading = section.heading or "Section"
    prefix = f"## {heading}\n\n"
    paragraphs = [part.strip() for part in section.body.split("\n\n") if part.strip()]
    if not paragraphs:
        return [
            StructuredChunk(
                content=section.body[:max_chunk_chars],
                section_titles=[heading],
                includes_document_header=includes_document_header,
            )
        ]

    raw_parts: list[str] = []
    current: list[str] = []
    current_len = len(prefix)

    for paragraph in paragraphs:
        paragraph_len = len(paragraph) + (2 if current else 0)
        if current and current_len + paragraph_len > max_chunk_chars:
            raw_parts.append(prefix + "\n\n".join(current))
            current = [paragraph]
            current_len = len(prefix) + len(paragraph)
            continue
        current.append(paragraph)
        current_len += paragraph_len

    if current:
        raw_parts.append(prefix + "\n\n".join(current))

    total = len(raw_parts)
    return [
        StructuredChunk(
            content=content.strip(),
            section_titles=[
                heading if total == 1 else f"{heading} (part {index}/{total})"
            ],
            includes_document_header=includes_document_header and index == 1,
        )
        for index, content in enumerate(raw_parts, start=1)
    ]


def _format_section(section: DocumentSection) -> str:
    body = section.body.strip()
    if section.heading is None:
        return body
    if body.startswith("## "):
        return body
    return f"## {section.heading}\n\n{body}"


def _sections_to_chunk(
    sections: list[DocumentSection],
    *,
    includes_document_header: bool,
) -> StructuredChunk:
    content = "\n\n".join(_format_section(section) for section in sections).strip()
    titles: list[str] = []
    has_header = False
    for section in sections:
        if section.heading:
            titles.append(section.heading)
        else:
            has_header = True
            if "Document header" not in titles:
                titles.insert(0, "Document header")
    return StructuredChunk(
        content=content,
        section_titles=titles or ["Content"],
        includes_document_header=includes_document_header and has_header,
    )


def _wrap_plain_chunks(chunks: list[str]) -> list[StructuredChunk]:
    wrapped: list[StructuredChunk] = []
    for index, chunk in enumerate(chunks):
        wrapped.append(
            StructuredChunk(
                content=chunk,
                section_titles=_section_titles_from_text(chunk),
                includes_document_header=index == 0 and _has_document_header(chunk),
            )
        )
    return wrapped


def _section_titles_from_text(text: str) -> list[str]:
    titles: list[str] = []
    for line in text.splitlines():
        heading = _detect_section_heading(line.strip())
        if heading:
            titles.append(heading)
    return titles or ["Content"]


def _has_document_header(text: str) -> bool:
    for line in text.splitlines()[:12]:
        if _HEADER_FIELD.match(line.strip()):
            return True
    return False


def _chunk_by_units(units: list[str], max_chunk_chars: int, *, joiner: str) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for unit in units:
        unit = unit.strip()
        if not unit:
            continue

        if len(unit) > max_chunk_chars:
            if current:
                chunks.append(joiner.join(current))
                current = []
                current_len = 0
            chunks.extend(_chunk_by_lines(unit, max_chunk_chars))
            continue

        added_len = len(unit) if not current else len(joiner) + len(unit)
        if current and current_len + added_len > max_chunk_chars:
            chunks.append(joiner.join(current))
            current = [unit]
            current_len = len(unit)
            continue

        current.append(unit)
        current_len += added_len

    if current:
        chunks.append(joiner.join(current))

    return [chunk for chunk in chunks if chunk.strip()]


def _chunk_by_lines(text: str, max_chunk_chars: int) -> list[str]:
    lines = text.splitlines()
    if not lines:
        return [text]

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in lines:
        line_len = len(line) + (1 if current else 0)
        if len(line) > max_chunk_chars:
            if current:
                chunks.append("\n".join(current))
                current = []
                current_len = 0
            for start in range(0, len(line), max_chunk_chars):
                chunks.append(line[start : start + max_chunk_chars])
            continue

        if current and current_len + line_len > max_chunk_chars:
            chunks.append("\n".join(current))
            current = [line]
            current_len = len(line)
            continue

        current.append(line)
        current_len += line_len

    if current:
        chunks.append("\n".join(current))

    return [chunk for chunk in chunks if chunk.strip()]
