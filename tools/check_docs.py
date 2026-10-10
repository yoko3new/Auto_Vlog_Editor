"""Validate local documentation routes, anchors and compact entrypoints.

Run from any directory: python3 tools/check_docs.py
Checks repository documents only; this does not validate application behavior.
"""
from pathlib import Path
import argparse
from collections import Counter
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
FILES = sorted(ROOT.glob('README*.md')) + sorted(ROOT.glob('AGENTS*.md'))
for folder in ('docs', 'contracts', 'resources') + (('agent-roles',) if args.include_local else ()):
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
            # Stable anchors are shared between language versions.
            if (parts.fragment == 'brand-logo'
                    or re.fullmatch(r's\d+(?:-\d+)?', parts.fragment)):
                if f'id="{parts.fragment}"' not in contents:
                    errors.append(f'{path.relative_to(ROOT)}: missing anchor {raw}')
    if 'archive' not in path.parts and re.search(r'第\s*\d+(?:\.\d+)?\s*节', text):
        errors.append(f'{path.relative_to(ROOT)}: stale numeric chapter reference')
for name, limit in [('README.md', 100), ('README.en.md', 100), ('AGENTS.md', 50), ('AGENTS.en.md', 50)]:
    count = len((ROOT / name).read_text().splitlines())
    if count > limit:
        errors.append(f'{name}: {count} lines exceeds compact entrypoint target {limit}')

# Every shared Markdown document has a full counterpart and a language switch.
english_sources = {'docs/vlogii-guide.md', 'docs/vlogii-validation.md', 'resources/README.md'}
shared = [p for p in FILES if not local_only(p)]
shared_set = set(shared)
document_languages = {}
counterparts = {}
for path in shared:
    if path.stem.endswith(('.en', '.zh')):
        continue
    relative = path.relative_to(ROOT).as_posix()
    language = 'en' if relative in english_sources else 'zh'
    counterpart = path.with_name(path.stem + ('.zh' if language == 'en' else '.en') + '.md')
    document_languages[path] = language
    document_languages[counterpart] = 'zh' if language == 'en' else 'en'
    counterparts[path] = counterpart
    counterparts[counterpart] = path
pairs = 0
for path in shared:
    if path.stem.endswith(('.en', '.zh')):
        continue
    relative = path.relative_to(ROOT).as_posix()
    language = 'en' if relative in english_sources else 'zh'
    counterpart = path.with_name(path.stem + ('.zh' if language == 'en' else '.en') + '.md')
    if counterpart not in shared_set:
        errors.append(f'{relative}: missing bilingual counterpart {counterpart.name}')
        continue
    pairs += 1
    for current, other, current_language in [(path, counterpart, language), (counterpart, path, 'zh' if language == 'en' else 'en')]:
        label = '中文' if current_language == 'en' else 'English'
        expected = f'[{label}]({other.name})'
        if expected not in '\n'.join(current.read_text().splitlines()[:5]):
            errors.append(f'{current.relative_to(ROOT)}: missing language switch {expected}')
    for pattern, label in [(r'(?ms)^```[^\n]*\n.*?^```\s*$', 'code blocks'), (r'<a id="[^"]+"></a>', 'stable anchors')]:
        if re.findall(pattern, path.read_text()) != re.findall(pattern, counterpart.read_text()):
            errors.append(f'{relative}: bilingual {label} differ')
    if Counter(re.findall(r'`[^`\n]*`', path.read_text())) != Counter(re.findall(r'`[^`\n]*`', counterpart.read_text())):
        errors.append(f'{relative}: bilingual inline code differs')
for path in shared:
    if path not in document_languages:
        errors.append(f'{path.relative_to(ROOT)}: orphan language version')
        continue
    # Code examples are identical in both languages; only prose navigation changes.
    prose = re.sub(r'(?ms)^```[^\n]*\n.*?^```\s*$', '', path.read_text())
    for match in re.finditer(r'(?<!!)\[[^\]\n]*\]\(([^\n)]+)\)', prose):
        parts = urlsplit(match.group(1).strip().strip('<>'))
        if parts.scheme or parts.netloc:
            continue
        target = (path.parent / unquote(parts.path)).resolve() if parts.path else path
        if target in document_languages and target != counterparts[path] and document_languages[target] != document_languages[path]:
            errors.append(f'{path.relative_to(ROOT)}: navigation changes language at {match.group(1)}')
for path in ((ROOT / 'agent-roles').glob('*.md') if args.include_local else []):
    if len(path.read_text().splitlines()) > 40:
        errors.append(f'{path.relative_to(ROOT)}: role template exceeds 40 lines')
if errors:
    print('\n'.join(errors))
    raise SystemExit(1)
print(f'PASS: {len(FILES)} Markdown files, {pairs} bilingual pairs, {links} local links; stable anchors, code blocks and compact entrypoints.')
print('LIMIT: no external URL checks, application behavior, media rendering, or Replit validation.')
