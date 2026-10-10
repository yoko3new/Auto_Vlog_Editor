"""Load and validate style templates (standard library only).

The structural checker covers exactly the JSON Schema keywords used by
templates/style_template.schema.json; semantic checks follow it.
"""

import json
import math
import re
from pathlib import Path

from ..storage import VlogiiError

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
SCHEMA_FILE = "style_template.schema.json"
SCHEMA = json.loads((TEMPLATE_DIR / SCHEMA_FILE).read_text(encoding="utf-8"))
REPOSITORY = Path(__file__).resolve().parents[3]
TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: type(v) is int,
    "number": lambda v: type(v) in (int, float),
    "boolean": lambda v: type(v) is bool,
    "null": lambda v: v is None,
}


class TemplateError(VlogiiError):
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
        need(
            type(value) is type(spec["const"]) and value == spec["const"],
            f"{path}: must be {spec['const']!r}",
        )
    if "enum" in spec:
        numeric = type(value) in (int, float)
        need(
            any(
                value == x and (type(value) is type(x) or (numeric and type(x) in (int, float)))
                for x in spec["enum"]
            ),
            f"{path}: not one of {spec['enum']}",
        )
    if "type" in spec:
        need(TYPES[spec["type"]](value), f"{path}: expected {spec['type']}")
    if isinstance(value, dict):
        props = spec.get("properties", {})
        missing = set(spec.get("required", [])) - value.keys()
        need(not missing, f"{path}: missing {sorted(missing)}")
        need(
            len(value) >= spec.get("minProperties", 0),
            f"{path}: needs at least {spec.get('minProperties')} entries",
        )
        extra = spec.get("additionalProperties", True)
        for key, item in value.items():
            if key in props:
                structural(item, props[key], f"{path}.{key}")
            elif extra is False:
                raise TemplateError(f"{path}: unknown field {key!r}")
            elif isinstance(extra, dict):
                structural(item, extra, f"{path}.{key}")
    elif isinstance(value, list):
        need(
            len(value) >= spec.get("minItems", 0),
            f"{path}: needs at least {spec.get('minItems')} items",
        )
        if spec.get("uniqueItems"):
            need(len({json.dumps(x) for x in value}) == len(value), f"{path}: duplicate items")
        for i, item in enumerate(value):
            if "items" in spec:
                structural(item, spec["items"], f"{path}[{i}]")
    elif isinstance(value, str):
        need(
            spec.get("minLength", 0) <= len(value) <= spec.get("maxLength", math.inf),
            f"{path}: length",
        )
        if "pattern" in spec:
            need(
                re.search(spec["pattern"], value) is not None,
                f"{path}: does not match {spec['pattern']}",
            )
    elif type(value) in (int, float):
        need(
            spec.get("minimum", -math.inf) <= value <= spec.get("maximum", math.inf),
            f"{path}: out of range",
        )


def semantic(t: dict, check_files: bool) -> None:
    def check_range(r: dict, path: str) -> None:
        need(r["min_s"] <= r["target_s"] <= r["max_s"], f"{path}: needs min_s <= target_s <= max_s")

    out = t["output"]
    need(
        (out["width"], out["height"]) in ((720, 1280), (1280, 720)),
        "output: only 720x1280 or 1280x720",
    )
    check_range(t["duration"], "duration")
    roles = [s["role"] for s in t["sections"]]
    need(roles.count("body") == 1, "sections: exactly one body section")
    need(roles.count("hook") <= 1, "sections: at most one hook")
    need(roles == sorted(roles, key=["hook", "body"].index), "sections: hook comes before body")
    fixed = 0.0
    for i, s in enumerate(t["sections"]):
        check_range(s["shot"], f"sections[{i}].shot")
        need(
            (s["length_s"] is None) == (s["role"] == "body"),
            f"sections[{i}]: only body has length_s null",
        )
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
        need(
            t["voiceover"]["supported"],
            "text.captions: transcript captions need voiceover.supported",
        )
    if check_files:
        profile = REPOSITORY / t["reference"]["profile"]
        need(profile.is_file(), f"reference.profile: {t['reference']['profile']} not found")


def validate(template: dict, check_files: bool = False) -> dict:
    """Check structure and meaning. ``check_files`` also requires the measured reference profile."""
    structural(template, SCHEMA)
    semantic(template, check_files)
    return template


def template_paths() -> list[Path]:
    return sorted(p for p in TEMPLATE_DIR.glob("*.json") if p.name != SCHEMA_FILE)


def load(template_id: str, check_files: bool = False) -> dict:
    if not re.fullmatch(r"[a-z0-9_]{3,64}", template_id):
        raise TemplateError("Unknown style.")
    path = TEMPLATE_DIR / f"{template_id}.json"
    if not path.is_file():
        raise TemplateError(f"Unknown style: {template_id}")
    template = json.loads(path.read_text(encoding="utf-8"))
    try:
        validate(template, check_files)
    except TemplateError as exc:
        raise TemplateError(f"{path.name}: {exc}") from None
    need(template["id"] == template_id, f"{path.name}: id must equal the file name")
    return template


def summaries() -> list[dict]:
    """What the web app shows when a user picks a style."""
    items = []
    for path in template_paths():
        t = load(path.stem)
        items.append(
            {
                "id": t["id"],
                "revision": t["revision"],
                "name": t["display_name"],
                "description": t["description"],
                "reference_url": t["reference"]["url"],
                "orientation": "portrait"
                if t["output"]["height"] > t["output"]["width"]
                else "landscape",
                "duration": {
                    "min": t["duration"]["min_s"],
                    "target": t["duration"]["target_s"],
                    "max": t["duration"]["max_s"],
                },
                "voiceover": t["voiceover"]["supported"],
            }
        )
    return items
