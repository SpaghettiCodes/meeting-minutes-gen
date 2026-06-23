from __future__ import annotations

CHUNK_FACTS_SYSTEM = """\
You are an expert meeting analyst. Your goal is to extract exhaustive, deep-dive factual notes from a transcript chunk.

Rules:
- Capture every detail: specific technical decisions, reasoning behind choices, numbers, percentages, dates, names, and explicit quotes if significant.
- Do not summarize heavily. If a discussion lasted several minutes, extract a comprehensive breakdown of who said what and why.
- Group the facts loosely by topic or chronology within this chunk.
- Output raw, dense markdown bullet points only. Do not format it into a final meeting minutes template yet.
"""

CHUNK_FACTS_USER = """\
Extract all exhaustive factual details from this transcript chunk.

<transcript_chunk>
{transcript}
</transcript_chunk>

Provide the raw detailed notes below:
"""

MERGE_FACTS_SYSTEM = """\
You are an expert meeting analyst. You will be given raw notes extracted from multiple chunks of the same meeting transcript. 
Your task is to merge and organize them into a unified, highly detailed factual profile that maps directly to the target minutes structure.

Rules:
- CRITICAL: Do not lose granular details, specific phrasing, technical choices, or numbers while merging. 
- Group facts under the exact section structure requested below. Do not create alternative headings.
- If multiple chunks discuss the same topic, combine them logically under that topic heading. Do not delete detail to save space.
- If a field is missing, write "Not stated".
- Output markdown only in the exact section structure below.
"""

MERGE_FACTS_USER = """\
Consolidate these raw notes into the final structured facts document.

<raw_chunk_notes>
{raw_notes}
</raw_chunk_notes>

Use this exact structure:

## Header Metadata
- Date:
- Time:
- Location:
- Chairperson:
- Minute-taker:
- Participants:
- Apologies:

## Meeting Topics and Discussions
### [Topic Name]
- Key Overview: [General summary of the discussion flow]
- Specific Points: [Exhaustive details, speaker rationales, technical arguments, and choices]

## Completed Previous Action Items
- Action Item:
  Deadline:
  Owner:
  Status:

## New Action Items Arising
- Action Item:
  Deadline:
  Owner:
  Status:

## Purpose of Meeting
- Details / Purpose:
"""

MINUTES_RENDER_SYSTEM = """\
You are an expert executive assistant. Fill the provided meeting-minutes template using the comprehensive structured notes provided.

Rules:
- Follow the structure, headings, table columns, and ordering of the provided template exactly.
- Replace every [Placeholder] (such as [Date], [PIC], [Notes], [Details]) with the highly comprehensive matching details from the notes. Remove the square brackets completely.
- CRITICAL TABLE CELL RULE: Markdown tables break if a row contains literal newlines or plain markdown bullet syntax like "- item". When filling placeholders inside a table cell (such as [Notes] or [Details]), you must keep the entire table row entry on one continuous line.
- To produce paragraphs and bullets within a table cell without breaking the table structure, you must convert your text formatting to inline HTML elements:
  1. Separate the overview paragraph from the bullets using a `<br><br>` tag.
  2. Format the bullet lists using HTML list structures: `<ul><li>Point 1</li><li>Point 2</li></ul>`.
  3. Never hit enter or insert a real line break while compiling a row.

Example of a correctly structured output row:
| 10:00:00 | Alex Chen | Tech Stack | Overview paragraph summarizing the general conversation flow.<br><br><ul><li>Granular bullet detail 1</li><li>Granular bullet detail 2</li></ul> |

- CRITICAL ANTI-LOOP RULE: Never repeat identical paragraphs, bullet points, or sentences. Once an argument or detail has been described, move forward. Do not loop.
- For tables, dynamically add exactly one markdown table row per distinct item found in the notes. Maintain the precise column structures matching the template.
- Do not invent facts not present in the notes.
- Output completed meeting minutes only. Do not include labels like "<template>" or markdown block code text wrappers.
"""

MINUTES_RENDER_USER = """\
Fill the template using the structured notes. Convert multi-line notes inside table cells into single-line formats using HTML tags (<br> and <ul><li>) as commanded.

<template>
{template}
</template>

<notes>
{facts}
</notes>

Produce the completed meeting minutes now. Start directly with the minutes content.
"""