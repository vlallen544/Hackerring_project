# Parsers: turn source files (PDF, PPTX, MD, TXT) into page-level chunks that keep source id + page number
import json
from dataclasses import asdict, dataclass
from pathlib import Path

@dataclass
class Chunk:
    source_id: str
    page: int
    text: str

    def to_dict(self):
        return asdict(self)

def parse_file(path, source_id=None):
    path = Path(path)
    source_id = source_id or path.stem
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        import pdfplumber
        chunks = []
        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text = (page.extract_text() or "").strip()
                if text:
                    chunks.append(Chunk(source_id, i, text))
        if not chunks:
            raise ValueError(f"{path.name}: no readable text (scanned PDF?)")
        return chunks

    if suffix == ".pptx":
        from pptx import Presentation
        chunks = []
        for i, slide in enumerate(Presentation(path).slides, start=1):
            parts = [s.text_frame.text for s in slide.shapes if s.has_text_frame]
            text = "\n".join(p for p in parts if p.strip()).strip()
            if text:
                chunks.append(Chunk(source_id, i, text))
        return chunks

    if suffix in (".md", ".txt"):
        # a line containing only ---page--- marks a page break
        pages = [p.strip() for p in path.read_text(encoding="utf-8").split("---page---")]
        return [Chunk(source_id, i, p) for i, p in enumerate(pages, start=1) if p]

    raise ValueError(f"Unsupported file type: {suffix}")

def load_sources(data_dir="sample_data"):
    """Reads sources.json and parses every listed file. Returns (source_metadata, all_chunks)."""
    data_dir = Path(data_dir)
    meta = json.loads((data_dir / "sources.json").read_text(encoding="utf-8"))
    chunks = []
    for src in meta["sources"]:
        chunks += parse_file(data_dir / src["file"], src["id"])
    return meta, chunks

def chunks_to_prompt(chunks):
    """Formats chunks so the model can see (and cite) exactly which source and page each text is from."""
    return "\n\n".join(f"<<SOURCE {c.source_id} | PAGE {c.page}>>\n{c.text}" for c in chunks)