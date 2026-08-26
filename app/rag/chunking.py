"""Splits markdown docs into per-section chunks (## headers), not
fixed-size windows with overlap. The doc set (postmortems, runbooks)
uses a consistent, author-controlled section structure, so splitting
on that boundary keeps each chunk a complete thought instead of an
arbitrary offset cut — no overlap needed since we're not guessing
where one idea ends and another begins.
"""

import re
from dataclasses import dataclass, field


@dataclass
class Chunk:
    text: str
    metadata: dict = field(default_factory=dict)


def parse_metadata_block(block: str) -> dict[str, str]:
    metadata = {}
    for line in block.strip().splitlines():
        match = re.match(r"\*\*(.+?):\*\*\s*(.+)", line)
        if match:
            key, value = match.groups()
            metadata[key.strip().lower().replace(" ", "_")] = value.strip()
    return metadata


def chunk_document(text: str, source_file: str) -> list[Chunk]:
    lines = text.strip().splitlines()
    title_line = lines[0]
    title = title_line.lstrip("# ").strip()
    doc_type = "postmortem" if title_line.startswith("# Postmortem:") else "runbook"

    body = "\n".join(lines[1:])
    preamble, *section_blocks = re.split(r"\n## ", body)

    base_metadata = {"source_file": source_file, "doc_type": doc_type, "title": title}
    if doc_type == "postmortem":
        base_metadata.update(parse_metadata_block(preamble))

    chunks = []
    for block in section_blocks:
        header, _, content = block.partition("\n")
        chunk_text = f"{title}\n\n## {header.strip()}\n{content.strip()}"
        chunk_metadata = {**base_metadata, "section": header.strip()}
        chunks.append(Chunk(text=chunk_text, metadata=chunk_metadata))
    return chunks
