# Shared project working guide

[中文](AGENTS.md) · **English**

The `kang` branch already has the Vlogii local web MVP; the original competition plan and contracts are retained as planning. Implement the corresponding code only after receiving explicit development tasks; progress is based on real evidence.

This document is a team-shared specification, applicable to the coding assistants chosen by members. Personal role templates, concurrency settings, and scheduling workflows are not team dependencies.

## Read only what the task needs

- When entering the project for the first time, read [README](README.en.md); to resume an unfinished task, read the relevant lines in [Current Progress](docs/status.en.md).
- For division of work, file ownership, and merging, read [Collaboration Guide](docs/collaboration.en.md).
- For modifying service boundaries/storage, read [Architecture](docs/architecture.en.md); for modifying interfaces/timelines, follow [Contract Navigation](docs/contracts.en.md) to locate sections and specific schemas.
- For frontend/rendering visuals, read [Visual Specifications](docs/visual-design.en.md); for acceptance, read [Acceptance Criteria](docs/acceptance.en.md).
- For deployment, read [Replit Verification](docs/deployment.en.md); for AI integration/clip selection, read [AI Testing](docs/ai-selection.en.md).
- For reference-reel style templates and the style lab tools, read [Style Templates](docs/style-templates.en.md).
- Do not recursively read all links; reuse valid, previously read information, and supplement reading only when tasks change.

## Scope and ownership

- See [MVP Feature Comparison](docs/mvp-coverage.en.md) for current implementation and gaps; see [Product Definition](docs/product.en.md) for original competition goals. That a schema can express V2/V3 does not mean it should be implemented now.
- A (Yang Kang) is in charge of the entire video generation pipeline, backend/AI/assets/rendering/title layout/contracts/integration; B (teammate) is in charge of frontend pages, interactions, styles, and API calls. Confirm the file scope of this task before making modifications.
- The current frontend uses `/api/vlogii` and [Current OpenAPI](docs/vlogii.openapi.json); legacy `/api` contracts and mocks cannot directly replace the current backend.
- Use independent working directories/worktrees for parallel development; do not modify the same file in parallel within shared directories, nor switch Git branches concurrently.
- Reviews are read-only by default; debugging consists of reproduction and diagnosis by default, and taking over modifications requires explicit file handoff to prevent the original developer from writing simultaneously.
- status/decisions are maintained centrally by integration owner A, who may delegate to coding assistants; other members provide evidence and update recommendations.
- Do not initiate unauthorized development on your own simply because a todo exists.

## Delivery

- When public contracts change, update schemas, samples, doubles, and callers simultaneously; explain compatibility impacts, and avoid each side guessing a different field.
- AI provides the plan, code calculates the timeline, and the renderer executes; upon failure, retain the old successful version; mocks do not count toward real acceptance.
- Run relevant checks based on changes. Documentation link check: `python3 tools/check_docs.py`.
- Contract checks: `PYTHONDONTWRITEBYTECODE=1 python3 contracts/validate_examples.py` and `PYTHONDONTWRITEBYTECODE=1 python3 contracts/collaboration/validate_collaboration.py`.
- Delivery must state goals, modified files/commits, actual check results, unverified items, and next steps; save logs to files, returning only summaries and evidence paths.
- Synchronize corresponding documentation only when related code/contracts/processes change; do not append every round's process to the overview.
- Assets, caches, secret keys, and private evaluation records are not committed to Git; actual license records and non-sensitive acceptance evidence should be retained.
