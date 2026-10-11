"""Check README links and code fences using only the Python standard library."""

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent


def main():
    readme = ROOT / "README.md"
    contents = readme.read_text(encoding="utf-8")
    errors = []
    fences = re.findall(r"^```.*$", contents, flags=re.MULTILINE)
    if len(fences) % 2:
        errors.append("README.md: unclosed code fence")
    prose = re.sub(r"(?ms)^```[^\n]*\n.*?^```\s*$", "", contents)
    links = 0
    for match in re.finditer(r"!?\[[^\]\n]*\]\(([^\n)]+)\)", prose):
        raw = match.group(1).strip().strip("<>")
        parts = urlsplit(raw)
        if parts.scheme or parts.netloc:
            continue
        links += 1
        target = (ROOT / unquote(parts.path)).resolve() if parts.path else readme
        if not target.exists():
            errors.append(f"README.md: missing {raw}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"PASS: README.md, {links} local links and images; balanced code fences.")


if __name__ == "__main__":
    main()
