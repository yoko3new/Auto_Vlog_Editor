"""Check README languages, links and code fences using the Python standard library."""

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent


def main():
    errors = []
    links = 0
    switches = {
        "README.md": "**English** | [简体中文](README.zh-CN.md)",
        "README.zh-CN.md": "[English](README.md) | **简体中文**",
    }
    for filename, switch in switches.items():
        readme = ROOT / filename
        if not readme.is_file():
            errors.append(f"Missing {filename}")
            continue
        contents = readme.read_text(encoding="utf-8")
        if switch not in contents.splitlines()[:5]:
            errors.append(f"{filename}: missing language switch at the top")
        if filename == "README.md" and re.search(r"[\u3400-\u9fff]", contents.replace(switch, "")):
            errors.append(f"{filename}: Chinese text outside the language switch")
        fences = re.findall(r"^```.*$", contents, flags=re.MULTILINE)
        if len(fences) % 2:
            errors.append(f"{filename}: unclosed code fence")
        prose = re.sub(r"(?ms)^```[^\n]*\n.*?^```\s*$", "", contents)
        for match in re.finditer(r"!?\[[^\]\n]*\]\(([^\n)]+)\)", prose):
            raw = match.group(1).strip().strip("<>")
            parts = urlsplit(raw)
            if parts.scheme or parts.netloc:
                continue
            links += 1
            target = (readme.parent / unquote(parts.path)).resolve() if parts.path else readme
            if not target.exists():
                errors.append(f"{filename}: missing {raw}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(
        f"PASS: {len(switches)} READMEs, {links} local links/images; language switches and code fences."
    )


if __name__ == "__main__":
    main()
