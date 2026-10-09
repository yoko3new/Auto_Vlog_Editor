"""Validate local documentation routes, anchors and compact entrypoints.

Run from any directory: python3 tools/check_docs.py
Checks repository documents only; this does not validate application behavior.
"""
from pathlib import Path
import argparse
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--include-local', action='store_true', help='Also check personal agent notes and historical archive if present.')
args = parser.parse_args()
def local_only(path):
    relative = path.relative_to(ROOT).as_posix()
    return (relative in ('docs/agent-workflow.md', 'LOCAL-DEVELOPMENT.md')
            or any(relative == folder or relative.startswith(folder + '/')
                   for folder in ('agent-roles', 'docs/archive', '.codex', '.agents', 'work', 'outputs')))
FILES = [ROOT / 'README.md', ROOT / 'AGENTS.md']
for folder in ('docs', 'contracts') + (('agent-roles',) if args.include_local else ()):
    FILES += sorted(p for p in (ROOT / folder).rglob('*.md') if args.include_local or not local_only(p))
if args.include_local and (ROOT / 'LOCAL-DEVELOPMENT.md').exists():
    FILES.append(ROOT / 'LOCAL-DEVELOPMENT.md')
errors = []
links = 0
for path in FILES:
    text = path.read_text()
    if sum(line.startswith('```') for line in text.splitlines()) % 2:
        errors.append(f'{path.relative_to(ROOT)}: unclosed code fence')
    for match in re.finditer(r'(?<!!)\[[^\]\n]*\]\(([^\n)]+)\)', text):
        raw = match.group(1).strip().strip('<>')
        parts = urlsplit(raw)
        if parts.scheme or parts.netloc:
            continue
        links += 1
        target = (path.parent / unquote(parts.path)).resolve() if parts.path else path
        if not args.include_local and target.is_relative_to(ROOT) and local_only(target):
            errors.append(f'{path.relative_to(ROOT)}: shared doc links to local-only content {raw}')
            continue
        if not target.exists():
            errors.append(f'{path.relative_to(ROOT)}: missing {raw}')
            continue
        if parts.fragment and target.suffix == '.md':
            contents = target.read_text()
            # Migrated section references use explicit stable HTML anchors.
            if parts.fragment.startswith('s') and re.fullmatch(r's\d+(?:-\d+)?', parts.fragment):
                if f'id="{parts.fragment}"' not in contents:
                    errors.append(f'{path.relative_to(ROOT)}: missing anchor {raw}')
    if 'archive' not in path.parts and re.search(r'第\s*\d+(?:\.\d+)?\s*节', text):
        errors.append(f'{path.relative_to(ROOT)}: stale numeric chapter reference')
for name, limit in [('README.md', 100), ('AGENTS.md', 50)]:
    count = len((ROOT / name).read_text().splitlines())
    if count > limit:
        errors.append(f'{name}: {count} lines exceeds compact entrypoint target {limit}')
for path in ((ROOT / 'agent-roles').glob('*.md') if args.include_local else []):
    if len(path.read_text().splitlines()) > 40:
        errors.append(f'{path.relative_to(ROOT)}: role template exceeds 40 lines')
if errors:
    print('\n'.join(errors))
    raise SystemExit(1)
print(f'PASS: {len(FILES)} Markdown files, {links} local links; stable section anchors and compact entrypoints.')
print('LIMIT: no external URL checks, application behavior, media rendering, or Replit validation.')
