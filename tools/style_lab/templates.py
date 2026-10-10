"""Load and validate style templates (stdlib only).

The structural checker covers exactly the JSON Schema keywords used by
style/templates/style_template.schema.json; semantic checks follow it.
Run: python3 tools/style_lab/templates.py
"""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = ROOT / "style" / "templates"
SCHEMA_FILE = "style_template.schema.json"
SCHEMA = json.loads((TEMPLATE_DIR / SCHEMA_FILE).read_text())
TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: type(v) is int,
    "number": lambda v: type(v) in (int, float),
    "boolean": lambda v: type(v) is bool,
    "null": lambda v: v is None,
}


class TemplateError(ValueError):
    pass


def need(condition: bool, message: str) -> None:
    if not condition:
        raise TemplateError(message)


def structural(value, spec: dict, path: str = "$") -> None:
    if "$ref" in spec:
        structural(value, SCHEMA["$defs"][spec["$ref"].split("/")[-1]], path)
        return
    if "oneOf" in spec:
        matches = 0
        for sub in spec["oneOf"]:
            try:
                structural(value, sub, path)
                matches += 1
            except TemplateError:
                pass
        need(matches == 1, f"{path}: oneOf matched {matches} branches")
    if "const" in spec:
        need(type(value) is type(spec["const"]) and value == spec["const"], f"{path}: must be {spec['const']!r}")
    if "enum" in spec:
        numeric = type(value) in (int, float)
        need(any(value == x and (type(value) is type(x) or (numeric and type(x) in (int, float)))
                 for x in spec["enum"]), f"{path}: not one of {spec['enum']}")
    if "type" in spec:
        need(TYPES[spec["type"]](value), f"{path}: expected {spec['type']}")
    if isinstance(value, dict):
        props = spec.get("properties", {})
        missing = set(spec.get("required", [])) - value.keys()
        need(not missing, f"{path}: missing {sorted(missing)}")
        need(len(value) >= spec.get("minProperties", 0), f"{path}: needs at least {spec.get('minProperties')} entries")
        extra = spec.get("additionalProperties", True)
        for key, item in value.items():
            if key in props:
                structural(item, props[key], f"{path}.{key}")
            elif extra is False:
                raise TemplateError(f"{path}: unknown field {key!r}")
            elif isinstance(extra, dict):
                structural(item, extra, f"{path}.{key}")
    elif isinstance(value, list):
        need(len(value) >= spec.get("minItems", 0), f"{path}: needs at least {spec.get('minItems')} items")
        if spec.get("uniqueItems"):
            need(len({json.dumps(x) for x in value}) == len(value), f"{path}: duplicate items")
        for i, item in enumerate(value):
            if "items" in spec:
                structural(item, spec["items"], f"{path}[{i}]")
    elif isinstance(value, str):
        need(spec.get("minLength", 0) <= len(value) <= spec.get("maxLength", math.inf), f"{path}: length")
        if "pattern" in spec:
            need(re.search(spec["pattern"], value) is not None, f"{path}: does not match {spec['pattern']}")
    elif type(value) in (int, float):
        need(spec.get("minimum", -math.inf) <= value <= spec.get("maximum", math.inf), f"{path}: out of range")


def semantic(t: dict) -> None:
    def check_range(r: dict, path: str) -> None:
        need(r["min_s"] <= r["target_s"] <= r["max_s"], f"{path}: needs min_s <= target_s <= max_s")

    out = t["output"]
    need((out["width"], out["height"]) in ((720, 1280), (1280, 720)), "output: only 720x1280 or 1280x720")
    check_range(t["duration"], "duration")
    roles = [s["role"] for s in t["sections"]]
    need(roles.count("body") == 1, "sections: exactly one body section")
    need(roles.count("hook") <= 1, "sections: at most one hook")
    need(roles == sorted(roles, key=["hook", "body"].index), "sections: hook comes before body")
    fixed = 0.0
    for i, s in enumerate(t["sections"]):
        check_range(s["shot"], f"sections[{i}].shot")
        need((s["length_s"] is None) == (s["role"] == "body"), f"sections[{i}]: only body has length_s null")
        fixed += s["length_s"] or 0.0
    if t["end_card"]:
        fixed += t["end_card"]["length_s"]
    need(fixed < t["duration"]["min_s"], "sections: hook and end card leave no room for the body")

    text = t["text"]
    used = [line["role"] for line in text["title"]["lines"]]
    used += [d["role"] for d in text["title"]["decorations"]]
    if text["stamps"]["mode"] != "none":
        used += [text["stamps"]["role"], text["stamps"]["caption_role"]]
    if text["captions"]["mode"] != "none":
        used.append(text["captions"]["role"])
    if t["end_card"]:
        used.append(t["end_card"]["text_role"])
    unknown = sorted(set(used) - text["roles"].keys())
    need(not unknown, f"text: undefined roles {unknown}")
    if text["title"]["show_until_s"] == "hook_end":
        need("hook" in roles, "text.title: show_until_s=hook_end needs a hook section")
    if text["captions"]["mode"] == "transcript":
        need(t["voiceover"]["supported"], "text.captions: transcript captions need voiceover.supported")
    need((ROOT / t["reference"]["profile"]).is_file(), f"reference.profile: {t['reference']['profile']} not found")


def validate(template: dict) -> dict:
    structural(template, SCHEMA)
    semantic(template)
    return template


def load(path_or_id: str | Path) -> dict:
    path = Path(path_or_id)
    if not path.suffix:
        path = TEMPLATE_DIR / f"{path_or_id}.json"
    template = json.loads(path.read_text())
    try:
        return validate(template)
    except TemplateError as exc:
        raise TemplateError(f"{path.name}: {exc}") from None


def template_paths() -> list[Path]:
    return sorted(p for p in TEMPLATE_DIR.glob("*.json") if p.name != SCHEMA_FILE)


def main() -> int:
    paths = template_paths()
    failures = 0
    for path in paths:
        try:
            template = load(path)
            need(template["id"] == path.stem, f"{path.name}: id must equal file name")
            print(f"ok   {path.name}")
        except TemplateError as exc:
            failures += 1
            print(f"FAIL {exc}")
    print(f"{len(paths) - failures}/{len(paths)} templates valid")
    return 1 if failures or not paths else 0


if __name__ == "__main__":
    sys.exit(main())
