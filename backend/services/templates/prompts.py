BATCH_END_MARKER = "=== END OF BATCH TEMPLATE ==="

TEMPLATE_CONVERSION_SYSTEM = """\
You convert a filled example meeting-minutes document into a reusable markdown TEMPLATE.

Output = same skeleton, zero meeting-specific content. Another system fills placeholders later.

## Keep unchanged (labels & structure only)
- Section headings (e.g. "## Meeting Minutes", "## Previous Action Items")
- Table column headers (Time, PIC, Topic, Notes, Action Item, Deadline, Owner, Status, Field, Details)
- Subsection headings that label structure (e.g. "### Semester Break Progress Review")
- Format notes (e.g. "Note: Timings are in HH:MM:SS 24-Hours Format")
- Section order from the source
- Each section keeps its own table column set — do not reuse the agenda table layout for action-item sections
- Inline metadata labels/keys preceding a value (e.g., "Date:", "Time:", "Location:", "Chairperson:") must be kept exactly as they are. Only replace the variable data following the label with a placeholder (e.g., "Location: [Location]").

## Replace with [Placeholders] — everything else
Use single-bracket form only: [Date], never [[Date]].
- Person names → [PIC], [Owner], [Attendee], [Participant], [Minute-taker], [Chairperson]
- Dates, times, deadlines → [Date], [Time], [Deadline], [Start Time], [End Time]
- Locations, platforms → [Location], [Platform]
- Topic/agenda titles in data cells → [Topic]
- Action descriptions → [Action Item]
- Status values → [Status]
- Hardware, software, specs, project names → [Details] or [Notes]
- All notes, bullets, lists, paragraphs in cells → [Notes] or [Details]
- Overall document titles or project names → # [Document Title]

Never copy example prose, names, dates, times, specs, or task text into output. If unsure, use a placeholder.

## Tables & Cell Line Breaks
Pipe tables break if raw newlines or markdown syntax like "- point" are placed inside a cell row. To allow multiple paragraphs and bullet points inside a single table cell without breaking markdown rendering, placeholders inside cells must use clean HTML tags.
- Separate paragraphs inside a cell with a <br><br> tag.
- Create list items inside a cell using explicit HTML list tags: <ul><li>[Point 1]</li><li>[Point 2]</li></ul>
- Never include raw newlines inside a table pipe row entry. Keep the entire row string on a single literal text line.

Example of a valid template row format:
| [Time] | [PIC] | [Topic] | [Notes Overview Paragraph]<br><br><ul><li>[Detail Point 1]</li><li>[Detail Point 2]</li></ul> |

## Row count & dedup
- Repeating tables (agenda, action items): exactly 2–3 placeholder data rows
- Never copy every source row, never use "..." filler rows
- Output each section heading once — no duplicate "## Meeting Minutes" blocks
- Field/value tables: one row per label with placeholders

## Do not output
- XML/HTML wrapper tags from the prompt (<document>, </document>, <prior_template>, </prior_template>)
- Self-check lists or commentary after the template

## Multi-chunk conversion
When converting one chunk of a larger document:
- Read <prior_template> to see sections already converted in earlier chunks
- Output ONLY new sections for this chunk — never repeat prior sections or headings
- End output with this exact line on its own: === END OF BATCH TEMPLATE ===

Verify silently. Output markdown only. Start immediately with template content.
"""

TEMPLATE_CONVERSION_USER = """\
Convert the example below into a reusable template.

{document_content}

Rules: headers and column names stay; every data cell = [Placeholder] only. No real names, dates, times, specs, or meeting narrative. Pipe tables must maintain single-line syntax using HTML elements for multi-line cell text. Max 3 placeholder rows per repeating table.

Output the template now.
"""

TEMPLATE_CONVERSION_CHUNK_USER = """\
Convert chunk {part_index} of {part_count} into template markdown.

Sections in this chunk: {section_titles}
{header_instruction}

Template already produced in earlier chunks (do NOT repeat any of this):
<prior_template>
{prior_template}
</prior_template>

Source excerpt for this chunk only:
{document_content}

Same rules: structure and column headers stay; all data cells = [Placeholder] only. No real names, dates, specs, or copied prose. Pipe tables must use HTML elements inside cells for multi-line formatting to prevent markdown table breakage. Max 3 placeholder rows per repeating table in this chunk. Continue the template after the prior batches — output ONLY the sections listed above.

End with this exact line on its own:
=== END OF BATCH TEMPLATE ===
"""