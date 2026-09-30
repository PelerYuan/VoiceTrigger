import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]


def check_docs(root=ROOT):
    failures = []
    pages = [root / name for name in ("README.md", "CONTRIBUTING.md", "SECURITY.md", "CHANGELOG.md")]
    pages.extend(sorted((root / "docs").rglob("*.md")))
    for page in pages:
        if not page.is_file():
            failures.append(f"Missing document: {page.relative_to(root)}")
            continue
        content = page.read_text(encoding="utf-8")
        content = re.sub(r"(?ms)^```.*?^```\s*$", "", content)
        for match in re.finditer(r"(?<!!)\[[^\]]+\]\(([^\s)]+)(?:\s+[^)]*)?\)", content):
            link = urlsplit(match.group(1))
            if link.scheme or link.netloc or not link.path:
                continue
            destination = (page.parent / unquote(link.path)).resolve()
            if not destination.is_relative_to(root.resolve()):
                failures.append(f"Out-of-project link: {page.relative_to(root)} -> {match.group(1)}")
            elif not destination.exists():
                failures.append(f"Broken link: {page.relative_to(root)} -> {match.group(1)}")
    configuration = (root / "mkdocs.yml").read_text(encoding="utf-8")
    navigation = re.findall(r"(?m)^\s+-\s+[^:]+:\s+(\S+\.md)\s*$", configuration)
    if not navigation:
        failures.append("No Markdown pages found in MkDocs navigation")
    for target in navigation:
        if not (root / "docs" / target).is_file():
            failures.append(f"Missing navigation page: {target}")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"Documentation links and {len(navigation)} navigation pages verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(check_docs())
