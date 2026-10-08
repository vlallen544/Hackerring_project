"""Document parsers — PDF, PPTX and plain text into `Chunk` records.

Only this layer touches files. Parsers return ordered chunks; the agents
never see raw file bytes, so a malformed upload cannot reach the model.
"""

from __future__ import annotations

import os
from typing import List

from backend.models import Chunk, Source

#: Fallback authority when a file type carries no source metadata.
DEFAULT_AUTHORITY = {
    "textbook": 0.9,
    "paper": 0.85,
    "notes": 0.6,
    "slides": 0.55,
    "url": 0.5,
    "jd": 0.7,
}


def _source_for(path: str, kind: str) -> Source:
    authority = DEFAULT_AUTHORITY.get(kind, 0.5)
    return Source(kind=kind, name=os.path.basename(path), authority=authority)


def parse_pdf(path: str, *, kind: str = "textbook") -> List[Chunk]:
    """Extract per-page text with pdfplumber."""
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pdfplumber not installed: pip install pdfplumber") from exc

    source = _source_for(path, kind)
    chunks: List[Chunk] = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = (page.extract_text() or "").strip()
            if not text:
                continue
            chunks.append(Chunk(
                source=source,
                page=i,
                text=text,
                quote=text[:280],
            ))
    return chunks


def parse_pptx(path: str, *, kind: str = "slides") -> List[Chunk]:
    """One chunk per slide, title preserved in the text body."""
    try:
        from pptx import Presentation
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("python-pptx not installed: pip install python-pptx") from exc

    source = _source_for(path, kind)
    chunks: List[Chunk] = []
    prs = Presentation(path)
    for i, slide in enumerate(prs.slides, start=1):
        lines: List[str] = []
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            for para in shape.text_frame.paragraphs:
                line = "".join(run.text for run in para.runs).strip()
                if line:
                    lines.append(line)
        body = "\n".join(lines).strip()
        if body:
            chunks.append(Chunk(source=source, page=i, text=body,
                                quote=body[:280]))
    return chunks


def parse_text(path: str, *, kind: str = "notes") -> List[Chunk]:
    """Plain text / Markdown / .txt notes — one chunk per paragraph block."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        raw = fh.read()
    source = _source_for(path, kind)
    chunks: List[Chunk] = []
    for i, block in enumerate(
        b.strip() for b in raw.split("\n\n") if b.strip()
    ):
        chunks.append(Chunk(source=source, page=i + 1, text=block,
                            quote=block[:280]))
    return chunks


def parse(path: str, *, kind: str | None = None) -> List[Chunk]:
    """Dispatch on file extension."""
    ext = os.path.splitext(path)[1].lower()
    kind = kind or DEFAULT_AUTHORITY.get(ext.lstrip("."), "notes")

    if ext == ".pdf":
        return parse_pdf(path, kind=kind)
    if ext in (".pptx", ".ppt"):
        return parse_pptx(path, kind=kind)
    if ext in (".txt", ".md", ".markdown", ".rst"):
        return parse_text(path, kind=kind)
    raise ValueError(f"unsupported file type: {ext or '(none)'}")
