"""Load documents from the corpus folder as plain Markdown-ish text.

Markdown files are read as-is. PDFs are converted with pypdf, one
"## Page N" heading per page, so the heading-aware chunker (Step 3) treats
both formats the same way and citations for PDFs point to a page.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

SUPPORTED = {".md", ".markdown", ".txt", ".pdf"}


@dataclass(frozen=True)
class Document:
    source_file: str  # file name relative to the corpus folder, e.g. "Parakh.md"
    text: str


def pdf_to_text(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        page_text = (page.extract_text() or "").strip()
        if page_text:  # skip blank / image-only pages
            pages.append(f"## Page {i}\n\n{page_text}")
    return "\n\n".join(pages)


def load_document(path: Path, root: Path) -> Document:
    if path.suffix.lower() == ".pdf":
        text = pdf_to_text(path)
    else:
        text = path.read_text(encoding="utf-8", errors="replace")
    return Document(source_file=path.relative_to(root).as_posix(), text=text)


def load_corpus(corpus_dir: str | Path = "corpus") -> list[Document]:
    """All supported files under corpus_dir, sorted by name for stable order."""
    root = Path(corpus_dir)
    files = sorted(
        p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED
    )
    docs = [load_document(p, root) for p in files]
    return [d for d in docs if d.text.strip()]
