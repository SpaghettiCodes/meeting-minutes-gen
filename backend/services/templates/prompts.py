from __future__ import annotations

TEMPLATE_CONVERSION_SYSTEM = """\
You convert a filled example meeting-minutes document into a reusable markdown TEMPLATE.

Output = same skeleton, zero meeting-specific content. Another system fills placeholders later.

## Keep unchanged (labels & structure only)
- Section headings (e.g. "## Meeting Minutes", "## Previous Action Items")
- Table column headers (Time, PIC, Topic, Notes, Action Item, Deadline, Owner, Status, \
Field, Details)
- Subsection headings that label structure (e.g. "### Semester Break Progress Review")
- Format notes (e.g. "Note: Timings are in HH:MM:SS 24-Hours Format")
- Section order from the source
- Each section keeps its own table column set — do not reuse the agenda table layout \
for action-item sections

## Replace with [Placeholders] — everything else
Use single-bracket form only: [Date], never [[Date]].
- Person names → [PIC], [Owner], [Attendee], [Participant], [Minute-taker], [Chairperson]
- Dates, times, deadlines → [Date], [Time], [Deadline], [Start Time], [End Time]
- Locations, platforms → [Location], [Platform]
- Topic/agenda titles in data cells → [Topic] — not "Opening & Attendance", \
"Review of Previous Action Items", etc.
- Action descriptions → [Action Item]
- Status values → [Status]
- Hardware, software, specs, project names → [Details] or [Notes]
- All notes, bullets, lists, paragraphs in cells → [Notes] or [Details]

Never copy example prose, names, dates, times, specs, or task text into output. \
If unsure, use a placeholder.

## Tables
Pipe tables or HTML tables are both fine. Pick whichever matches the source layout.
- Pipe table: header | separator | body rows
- HTML table: valid <table> with <thead>/<tbody>, lists in cells may use <ul>/<ol>
- No grid/ascii tables (+---+, || double pipes)
- No pandoc plain-text tables (dashed lines, aligned columns without pipes)
- No code fences (```)
- No broken or partial table syntax

Example field table (pipe or HTML both OK):

| Field    | Details    |
|----------|------------|
| Location | [Location] |
| Date     | [Date]     |

## Row count & dedup
- Repeating tables (agenda, action items): exactly 2–3 placeholder data rows
- Never copy every source row, never use "..." filler rows
- Output each section heading once — no duplicate "## Meeting Minutes" blocks
- Field/value tables: one row per label with placeholders

## Do not output
- XML/HTML wrapper tags from the prompt (<document>, </document>)
- Self-check lists or commentary after the template

Verify silently. Output markdown only. Start immediately with template content.
"""

TEMPLATE_CONVERSION_USER = """\
Convert the example below into a reusable template.

{document_content}

Rules: headers and column names stay; every data cell = [Placeholder] only. \
No real names, dates, times, specs, or meeting narrative. \
Pipe or HTML tables OK. Max 3 placeholder rows per repeating table. \
Each section uses its correct column headers.

Output the template now.
"""

TEMPLATE_CONVERSION_CHUNK_USER = """\
Convert chunk {part_index} of {part_count} into template markdown.

Sections in this chunk: {section_titles}
{header_instruction}

{document_content}

Same rules: structure and column headers stay; all data cells = [Placeholder] only. \
No real names, dates, specs, or copied prose. Pipe or HTML tables OK. \
Max 3 placeholder rows per repeating table in this chunk. \
Output ONLY the sections listed above — do not add other sections or repeat content \
from earlier chunks.

Output this chunk now.
"""

TEMPLATE_REPAIR_SYSTEM = """\
You fix a broken draft meeting-minutes TEMPLATE.

Problems to fix:
- Duplicate section headings — keep one of each
- Grid/ascii tables (+---+, ||) — delete or replace with pipe/HTML tables
- Pandoc plain-text tables (dashed lines, no pipes) — replace with pipe or HTML tables
- Wrong table schema: "Previous Action Items" and "New Action Items" must use \
Action Item | Deadline | Owner | Status — not Time/PIC/Topic
- Broken rows (stray |], misaligned pipes) — delete or rewrite as valid rows
- Invented placeholders ([Blank Row], [Sub Blank row]) — remove those rows
- Real meeting content in cells — replace with [Placeholder] tokens
- Double-bracket placeholders [[Date]] → [Date]
- XML tags (<document>, </document>) — remove
- Trailing backslashes on lines — remove

Keep valid section headings, column headers, and format notes.
Every data cell = [Placeholder] only. Pipe or HTML tables OK.
Output fixed template only. No commentary.
"""

TEMPLATE_REPAIR_USER = """\
Fix this draft template:

{draft}

Output the corrected template now.
"""
