"""Test local Markdown link integrity across the repository."""

import re
from pathlib import Path


def test_markdown_local_links() -> None:
    """Verify that all relative local links in Markdown files resolve to existing files or directories."""
    repo_root = Path(__file__).parent.parent
    md_files = list(repo_root.glob("**/*.md"))

    # Exclude virtual environments or build caches if any exist
    md_files = [
        f for f in md_files if ".venv" not in f.parts and ".pytest_cache" not in f.parts
    ]

    # Pattern matches [text](link) where link is local (not http/https/mailto)
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

    broken_links = []

    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8")
        matches = link_pattern.findall(content)

        for text, target in matches:
            target = target.strip()

            # Ignore external links, mailto, or fragment-only links
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue

            # Strip fragment anchor if present
            target_path_str = target.split("#")[0]
            if not target_path_str:
                continue  # Link was just an anchor like (#section)

            # Resolve target path relative to the file containing the link
            if target_path_str.startswith("/"):
                resolved_path = (repo_root / target_path_str.lstrip("/")).resolve()
            else:
                resolved_path = (md_file.parent / target_path_str).resolve()

            if not resolved_path.exists():
                broken_links.append(
                    (str(md_file.relative_to(repo_root)), target, str(resolved_path))
                )

    assert not broken_links, "Found broken Markdown local links:\n" + "\n".join(
        f"In {src}: link '{link}' resolves to missing '{resolved}'"
        for src, link, resolved in broken_links
    )
