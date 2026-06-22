from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextDocument:
    name: str
    content: str


@dataclass(frozen=True)
class SavedFile:
    name: str


@dataclass(frozen=True)
class GeneratedMinutes:
    output_name: str
    content: str
