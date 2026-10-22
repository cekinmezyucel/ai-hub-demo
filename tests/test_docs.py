import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
BUG_DOCS = ROOT / "docs" / "features" / "3-redirect-location-exact-url"
CLAIMS = ("exactly", "as sent", "unchanged", "<original url>")


def _readme_follow_link_block():
    lines = (ROOT / "README.md").read_text().splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("- `GET /{code}`"))
    block = []
    for line in lines[start:]:
        if not line.strip():
            break
        block.append(line)
    return "\n".join(block)


def test_readme_states_location_encoding():
    block = _readme_follow_link_block()

    assert "percent-encoded" in block
    assert any(example in block for example in ("%7C", "%7B", "%C3%A9"))
    assert "exactly as sent" not in block
    assert "<original URL>" not in block


def _doc_files():
    yield ROOT / "README.md"
    for path in (ROOT / "docs").rglob("*.md"):
        if BUG_DOCS not in path.parents:
            yield path
    yield from (ROOT / "app").rglob("*.py")


def test_no_doc_says_location_is_url_as_sent():
    found = []
    for path in _doc_files():
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            text = line.lower()
            if not re.search(r"location|redirect", text):
                continue
            if any(claim in text for claim in CLAIMS) and "encod" not in text:
                found.append(f"{path.relative_to(ROOT)}:{number}")

    assert not found, "Location claimed to be the URL as sent: " + ", ".join(found)
