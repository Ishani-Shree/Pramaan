import pytest

from app.chunker import chunk_markdown, split_sections, window_words


def headings(md: str) -> list[str]:
    return [s.heading for s in split_sections(md)]


# ---------------------------------------------------------------- headings

def test_heading_path_follows_nesting():
    md = "# A\na\n## B\nb\n### C\nc\n## D\nd"
    assert headings(md) == ["A", "A > B", "A > B > C", "A > D"]


def test_text_before_first_heading_has_empty_heading():
    assert headings("intro text\n# A\nbody") == ["", "A"]


def test_hash_inside_code_fence_is_not_a_heading():
    md = "# A\n```bash\n# install deps\npip install x\n```\n## B\nb"
    sections = split_sections(md)
    assert [s.heading for s in sections] == ["A", "A > B"]
    assert "# install deps" in sections[0].body


def test_longer_fence_is_not_closed_by_shorter_one():
    md = "# A\n````\n```\n# still code\n```\n````\n## B\nb"
    assert headings(md) == ["A", "A > B"]


def test_tilde_fence():
    assert headings("# A\n~~~\n# code\n~~~\n## B\nb") == ["A", "A > B"]


def test_hashtag_without_space_is_not_a_heading():
    assert headings("# A\n#hashtag text\n") == ["A"]


def test_heading_markup_is_cleaned():
    md = "## **Bold** [link](http://x) `code` ##\nbody"
    assert headings(md) == ["Bold link code"]


def test_image_only_section_is_dropped_and_rules_stripped():
    md = "# A\nreal text\n\n---\n## Screenshots\n![x](a.png)\n\n---\n## C\nc"
    sections = split_sections(md)
    assert [s.heading for s in sections] == ["A", "A > C"]
    assert sections[0].body == "real text"  # trailing --- removed


def test_empty_document():
    assert split_sections("") == []
    assert chunk_markdown("f.md", "   \n\n") == []


# ---------------------------------------------------------------- windows

def test_window_overlap():
    text = " ".join(f"w{i}" for i in range(1, 11))
    windows = window_words(text, size=4, overlap=2)
    assert windows == ["w1 w2 w3 w4", "w3 w4 w5 w6", "w5 w6 w7 w8", "w7 w8 w9 w10"]
    for a, b in zip(windows, windows[1:]):
        assert a.split()[-2:] == b.split()[:2]  # exactly `overlap` words shared


def test_no_window_is_pure_overlap():
    # 6 words, size 4, overlap 2: a third window would only repeat w5 w6.
    assert window_words("a b c d e f", 4, 2) == ["a b c d", "c d e f"]


def test_text_that_fits_gives_one_window():
    assert window_words("a b c", 4, 2) == ["a b c"]


def test_window_keeps_newlines():
    assert window_words("line1\nline2\n  indented", 10, 0) == ["line1\nline2\n  indented"]


@pytest.mark.parametrize("size,overlap", [(0, 0), (4, 4), (4, 5), (4, -1)])
def test_invalid_window_params(size, overlap):
    with pytest.raises(ValueError):
        window_words("a b c", size, overlap)
    with pytest.raises(ValueError):
        chunk_markdown("f.md", "# A\na b c", size, overlap)


# ---------------------------------------------------------------- packing

def test_small_sections_are_packed_with_subheadings():
    md = "# P\nintro\n## A\naaa\n## B\nbbb"
    chunks = chunk_markdown("f.md", md, size=50, overlap=5)
    assert len(chunks) == 1
    assert chunks[0].heading == "P > A | B"
    assert chunks[0].text == "intro\n\n### A\naaa\n\n### B\nbbb"


def test_packing_respects_size():
    md = "# P\n## A\n" + "a " * 30 + "\n## B\n" + "b " * 30
    chunks = chunk_markdown("f.md", md, size=40, overlap=5)
    assert [c.heading for c in chunks] == ["P > A", "P > B"]


def test_oversized_section_is_windowed_alone():
    md = "# P\n## Small\nsmall\n## Big\n" + " ".join(f"x{i}" for i in range(25))
    chunks = chunk_markdown("f.md", md, size=10, overlap=2)
    assert chunks[0].heading == "P > Small"
    big = [c for c in chunks if c.heading == "P > Big"]
    assert len(big) == 3  # 25 words, step 8: 0-10, 8-18, 16-25
    assert all(c.word_count <= 10 for c in big)


def test_chunk_index_is_sequential_and_source_kept():
    md = "# P\n## A\n" + "a " * 30 + "\n## B\n" + "b " * 30
    chunks = chunk_markdown("docs/f.md", md, size=20, overlap=5)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert {c.source_file for c in chunks} == {"docs/f.md"}
