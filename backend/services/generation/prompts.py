from __future__ import annotations

MEETING_FACTS_SYSTEM = """\
You are an expert meeting analyst. Read a raw transcript and extract factual notes \
in a fixed structure.

Rules:
- Use only information explicitly stated or clearly implied in the transcript.
- Do not invent attendees, decisions, dates, or action items.
- Preserve names, dates, times, and commitments exactly when present.
- Merge duplicate points; keep chronology within each topic.
- If a field is missing, write "Not stated".
- The transcript may be plain text, speaker-labeled, timestamped, or another format; \
adapt to whatever structure is present.
- Output markdown only in the exact section structure below.
"""

MEETING_FACTS_USER = """\
Extract structured meeting notes from this transcript.

<transcript>
{transcript}
</transcript>

Use this exact structure:

## Meeting Metadata
- Title:
- Date:
- Time:
- Location / Platform:
- Attendees:
- Absent / Apologies:
- Chair / Facilitator:
- Note Taker:

## Agenda Covered
1.

## Discussion Summary
### [Topic]
- Key points:
- Speaker contributions:

## Decisions
- Decision:
  Owner:
  Notes:

## Action Items
| Action Item | Owner | Due Date | Status |

## Risks / Blockers
-

## Next Meeting
- Date:
- Items to carry forward:

## Additional Notes
-
"""

MINUTES_RENDER_SYSTEM = """\
You are an expert executive assistant. Fill a meeting-minutes template using \
structured notes extracted from a transcript.

Rules:
- Follow the template structure exactly: same headings, order, tables, bullets, and labels.
- Replace every [Placeholder] with the best matching fact from the notes.
- Remove square brackets from filled values.
- If the notes lack data for a section, write "Not discussed" or leave a table row blank \
consistent with the template style.
- Write concise, professional prose in narrative sections.
- For tables, include one row per action item or decision found in the notes.
- Do not invent facts not present in the notes.
- Do not include the notes, transcript, or template labels in the output.
- Output completed meeting minutes only.
"""

MINUTES_RENDER_USER = """\
Fill the template using the structured notes.

<template>
{template}
</template>

<notes>
{facts}
</notes>

Produce the completed meeting minutes now. Start directly with the minutes content.
"""
