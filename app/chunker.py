"""Heading-aware chunking for Markdown.

Two passes:
  1. split_sections(): cut the document at Markdown headings (ignoring '#'
     lines inside fenced code blocks). Each section remembers its full heading
     path, e.g. "Parakh > Setup > Running locally".
  2. window_words(): cut each section into windows of `size` words that
     overlap by `overlap` words. A window never crosses a heading boundary.

Original whitespace (newlines, code indentation) is kept inside a chunk, so
the LLM sees code blocks and lists as they were written.

CLI (prints statistics, writes nothing):
    python -m app.chunker corpus --size 300 --overlap 50
"""

from __future__ import annotations

import argparse
import re
import statistics
from dataclasses import dataclass

DEFAULT_SIZE = 300
DEFAULT_OVERLAP = 50

# ATX heading: up to 3 spaces, 1-6 '#', a space, the title, optional closing #s.
HEADING_RE = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$")
# Fence opener: ``` or ~~~ (3+), optionally followed by a language name.
FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
# A word plus the whitespace after it, so joining tokens restores the layout.
TOKEN_RE = re.compile(r"\S+\s*")
HEADING_SEP = " > "


@dataclass(frozen=True)
class Section:
    heading: str  # full heading path, "" for text before the first heading
    body: str


@dataclass(frozen=True)
class Chunk:
    source_file: str
    heading: str
    chunk_index: int  # position within its file, 0-based
    text: str

    @property
    def word_count(self) -> int:
        return len(self.text.split())


def _clean_title(title: str) -> str:
    title = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", title)  # images -> alt text
    title = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", title)  # links -> link text
    title = re.sub(r"<[^>]+>", "", title)  # inline HTML
    title = title.replace("**", "").replace("__", "").replace("`", "")
    return " ".join(title.split())


RULE_RE = re.compile(r"^ {0,3}([-*_])( *\1){2,} *$")  # ---, ***, ___
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_rules(body: str) -> str:
    """Drop horizontal-rule lines at the start/end of a section (separators)."""
    lines = body.strip().splitlines()
    while lines and RULE_RE.match(lines[0]):
        lines.pop(0)
    while lines and RULE_RE.match(lines[-1]):
        lines.pop()
    return "\n".join(lines).strip()


def _has_text(body: str) -> bool:
    """False for sections that are only images / HTML / rules (e.g. a
    'Screenshots' section): they carry no answerable text, only noise."""
    rest = HTML_TAG_RE.sub(" ", IMAGE_RE.sub(" ", body))
    rest = "\n".join(l for l in rest.splitlines() if not RULE_RE.match(l))
    return bool(re.search(r"\w", rest))


def split_sections(text: str) -> list[Section]:
    """Split Markdown into sections at headings. Sections with no real text
    (empty, or only images/rules) are dropped."""
    sections: list[Section] = []
    stack: list[tuple[int, str]] = []  # (level, title) of the open headings
    buf: list[str] = []
    fence: str | None = None  # the fence string we are inside, if any

    def flush() -> None:
        body = _strip_rules("\n".join(buf))
        if _has_text(body):
            heading = HEADING_SEP.join(t for _, t in stack if t)
            sections.append(Section(heading=heading, body=body))
        buf.clear()

    for line in text.splitlines():
        if fence is not None:
            buf.append(line)
            # Closing fence: same character, at least as long, nothing after it.
            stripped = line.strip()
            if (
                stripped
                and set(stripped) == {fence[0]}
                and len(stripped) >= len(fence)
            ):
                fence = None
            continue

        opener = FENCE_OPEN_RE.match(line)
        if opener:
            fence = opener.group(1)
            buf.append(line)
            continue

        heading = HEADING_RE.match(line)
        if heading:
            flush()
            level = len(heading.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, _clean_title(heading.group(2))))
            continue

        buf.append(line)

    flush()
    return sections


def window_words(text: str, size: int, overlap: int) -> list[str]:
    """Split text into windows of `size` words, consecutive windows sharing
    `overlap` words. The last window may be shorter; no window is ever pure
    overlap (i.e. fully contained in the previous one)."""
    if size < 1:
        raise ValueError("size must be >= 1")
    if not 0 <= overlap < size:
        raise ValueError("overlap must satisfy 0 <= overlap < size")

    tokens = TOKEN_RE.findall(text)
    if not tokens:
        return []
    step = size - overlap
    windows: list[str] = []
    start = 0
    while True:
        windows.append("".join(tokens[start : start + size]).strip())
        if start + size >= len(tokens):
            break
        start += step
    return windows


def _words(text: str) -> int:
    return len(text.split())


def _path(heading: str) -> list[str]:
    return heading.split(HEADING_SEP) if heading else []


def pack_sections(sections: list[Section], size: int) -> list[list[Section]]:
    """Greedily group consecutive sections so each group has <= `size` body
    words. A section bigger than `size` is put in a group of its own (it is
    split into overlapping windows later). Groups only ever break at a
    heading, never in the middle of a section."""
    groups: list[list[Section]] = []
    current: list[Section] = []
    current_words = 0
    for section in sections:
        n = _words(section.body)
        if current and (current_words + n > size or n > size):
            groups.append(current)
            current, current_words = [], 0
        current.append(section)
        current_words += n
        if n > size:  # oversized: always alone
            groups.append(current)
            current, current_words = [], 0
    if current:
        groups.append(current)
    return groups


def _group_heading(paths: list[list[str]]) -> tuple[list[str], str]:
    """Common heading prefix of a group, plus a display heading.
    e.g. ["Parakh","Setup","Backend"], ["Parakh","Setup","Frontend"]
         -> prefix ["Parakh","Setup"], heading "Parakh > Setup > Backend | Frontend"."""
    prefix: list[str] = []
    for parts in zip(*paths):
        if len(set(parts)) != 1:
            break
        prefix.append(parts[0])
    children: list[str] = []
    for p in paths:
        if len(p) > len(prefix) and p[len(prefix)] not in children:
            children.append(p[len(prefix)])
    display = prefix + ([" | ".join(children)] if len(children) > 1 else children)
    return prefix, HEADING_SEP.join(display)


def chunk_markdown(
    source_file: str,
    text: str,
    size: int = DEFAULT_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[Chunk]:
    """Heading split -> pack small neighbouring sections up to `size` words ->
    window any section still bigger than `size` with `overlap`.

    `size` counts body words; the sub-heading lines added inside a merged
    chunk (e.g. "### Backend") come on top of that."""
    if size < 1 or not 0 <= overlap < size:
        raise ValueError("need size >= 1 and 0 <= overlap < size")

    chunks: list[Chunk] = []

    def add(heading: str, piece: str) -> None:
        chunks.append(Chunk(source_file, heading, len(chunks), piece))

    for group in pack_sections(split_sections(text), size):
        if len(group) == 1:
            section = group[0]
            for piece in window_words(section.body, size, overlap):
                add(section.heading, piece)
            continue

        # Merged chunk: keep each sub-section's heading inside the text so the
        # LLM (and the embedding) can still tell the parts apart.
        paths = [_path(s.heading) for s in group]
        prefix, heading = _group_heading(paths)
        parts = []
        for section, path in zip(group, paths):
            relative = HEADING_SEP.join(path[len(prefix):])
            parts.append(f"### {relative}\n{section.body}" if relative else section.body)
        add(heading, "\n\n".join(parts))
    return chunks


def chunk_corpus(docs, size: int = DEFAULT_SIZE, overlap: int = DEFAULT_OVERLAP) -> list[Chunk]:
    """Chunk a list of app.loader.Document objects."""
    out: list[Chunk] = []
    for doc in docs:
        out.extend(chunk_markdown(doc.source_file, doc.text, size, overlap))
    return out


def _main() -> None:
    from app.loader import load_corpus

    parser = argparse.ArgumentParser(description="Chunk the corpus and print stats.")
    parser.add_argument("corpus", nargs="?", default="corpus")
    parser.add_argument("--size", type=int, default=DEFAULT_SIZE)
    parser.add_argument("--overlap", type=int, default=DEFAULT_OVERLAP)
    parser.add_argument("--show", type=int, default=0, help="print the first N chunks")
    args = parser.parse_args()

    docs = load_corpus(args.corpus)
    chunks = chunk_corpus(docs, args.size, args.overlap)
    counts = [c.word_count for c in chunks]

    print(f"size={args.size} overlap={args.overlap}")
    print(f"{'file':<40} {'sections':>8} {'chunks':>7}")
    for doc in docs:
        n_sec = len(split_sections(doc.text))
        n_chk = sum(c.source_file == doc.source_file for c in chunks)
        print(f"{doc.source_file:<40} {n_sec:>8} {n_chk:>7}")
    print(f"\nfiles={len(docs)} chunks={len(chunks)}")
    if counts:
        print(
            f"words/chunk: min={min(counts)} median={statistics.median(counts):.0f} "
            f"max={max(counts)}  (<20 words: {sum(c < 20 for c in counts)})"
        )
    for c in chunks[: args.show]:
        print(f"\n--- [{c.source_file} #{c.chunk_index}] {c.heading} ({c.word_count} words)")
        print(c.text[:500])


if __name__ == "__main__":
    _main()
