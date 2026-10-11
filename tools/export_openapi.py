"""Generate or check the public API snapshot without starting the server."""

import argparse
import json
from pathlib import Path

from vlogii.api import create_app

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "api" / "openapi.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if the snapshot is stale.")
    args = parser.parse_args()
    schema = create_app().openapi()
    if args.check:
        if not SNAPSHOT.is_file() or json.loads(SNAPSHOT.read_text(encoding="utf-8")) != schema:
            parser.exit(1, "API snapshot is stale. Run: uv run python tools/export_openapi.py\n")
        print("PASS: api/openapi.json matches the FastAPI application.")
        return
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("Updated api/openapi.json")


if __name__ == "__main__":
    main()
