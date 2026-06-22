#!/usr/bin/env python3
"""CLI entry point for generating meeting minutes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from backend.models.config import ENV_FILE, load_config
from backend.services.exceptions import ServiceError
from backend.services.generation import GenerationService

TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".text"}


def pick_single_file(directory: Path, label: str, explicit: Path | None = None) -> Path:
    if explicit is not None:
        if not explicit.is_file():
            raise FileNotFoundError(f"{label} file not found: {explicit}")
        return explicit

    if not directory.is_dir():
        raise FileNotFoundError(f"{label} directory not found: {directory}")

    candidates = sorted(
        p for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in TEXT_EXTENSIONS and not p.name.startswith(".")
    )
    if not candidates:
        raise FileNotFoundError(
            f"No text files found in {label} directory: {directory}\n"
            f"Supported extensions: {', '.join(sorted(TEXT_EXTENSIONS))}"
        )
    if len(candidates) > 1:
        names = "\n  - ".join(p.name for p in candidates)
        raise ValueError(
            f"Multiple {label} files found in {directory}. "
            f"Specify one with --{label.lower()}-file:\n  - {names}"
        )
    return candidates[0]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate meeting minutes from a transcript and template."
    )
    parser.add_argument(
        "--transcript-file",
        type=Path,
        help="Path to a specific transcript file (overrides TRANSCRIPT_DIR auto-pick).",
    )
    parser.add_argument(
        "--template-file",
        type=Path,
        help="Path to a specific template file (overrides TEMPLATE_DIR auto-pick).",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        help="Path for the generated minutes (default: OUTPUT_DIR/{date}-{id}.md).",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=ENV_FILE,
        help="Path to .env file (default: project root .env.backend).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config = load_config(args.env_file)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    try:
        transcript_path = pick_single_file(
            config.transcript_dir, "Transcript", args.transcript_file
        )
        template_path = pick_single_file(
            config.template_dir, "Template", args.template_file
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    output_path = args.output_file

    print(f"Transcript: {transcript_path}")
    print(f"Template:   {template_path}")
    print(f"Model:      {config.llm_model}")
    print(f"Endpoint:   {config.llm_base_url}")
    print("Generating meeting minutes...")

    service = GenerationService(config)
    try:
        result = service.generate(
            transcript_name=transcript_path.name,
            template_name=template_path.name,
            output_path=output_path,
        )
    except ServiceError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    saved_path = output_path or (config.output_dir / result.output_name)
    print(f"Saved: {saved_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
