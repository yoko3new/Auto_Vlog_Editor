# Data and Interface Navigation

[中文](contracts.md) · **English**

[Back to Overview](../README.en.md). Locate by task first; there is no need to read the entire schema or all examples.

## Current Vlogii Interfaces

`kang` The current frontend uses `/api/vlogii`; see [Current OpenAPI](vlogii.openapi.json) for the structure and `/openapi.json` for the runtime; local models are in [models.py](../src/vlogii/models.py), and HTTP request/response models are in [api.py](../src/vlogii/api.py). A (Yang Kang) maintains the backend, models, and video modules, and B (teammate) maintains frontend invocations.

The table below contains the original competition `/api` and data/rendering contracts, retained for planning; compatibility mappings with the current Vlogii have not been implemented. Fields and states from old mocks cannot be directly used on the current page; future migrations must explicitly synchronize definitions, examples, and callers.

## Three Types of Boundaries in the Original Competition

| What to Hand Over | Structural Basis | Semantics and Examples |
| --- | --- | --- |
| Project settings, assets, editing plans, timelines, modification results, transcripts | [JSON Schema](../contracts/contracts.schema.json) | [Timeline Semantics](reference/timeline.en.md), [13 Data Examples](../contracts/examples/) |
| Browser ↔ backend requests/responses | [OpenAPI](../contracts/collaboration/api.openapi.json) | [HTTP Description](reference/api.en.md#s10-2), [31 HTTP Examples](../contracts/collaboration/api.examples.json) |
| A's internal scheduling ↔ layout/rendering | [Python Interface Types](../contracts/collaboration/runtime_contracts.py) | [Function Handover](reference/api.en.md#s10-6), [Mock Usage](../contracts/collaboration/README.en.md) |

Existing data `schema_version` and HTTP `api_version` are both `1.0.0` and are maintained independently. The `Data_*` copied within OpenAPI must remain consistent with the root JSON Schema, which the check script verifies. For product stage constraints, see [Product Scope](product.en.md#s2); features cannot be enabled merely because the schema is valid.

## Read by Task

| Current Task | Necessary Reference |
| --- | --- |
| Asset registration and local paths | [Asset Description](reference/timeline.en.md#s6-3), [Architecture and Storage](architecture.en.md#s11) |
| AI output plans | [Plan Fields](reference/timeline.en.md#s6-5), [AI Footage Selection Evaluation](ai-selection.en.md#s20-4) |
| Compiling or rendering timelines | [Second/Frame Conventions](reference/timeline.en.md#s6-2), [Timeline](reference/timeline.en.md#s6-6), [Validation Rules](reference/timeline.en.md#s6-10) |
| Titles, warmth, deletion, undo | [Modification Operations](reference/timeline.en.md#s6-8), [Editing and Versions](reference/editing.en.md#s9) |
| Upload, polling, errors, playback | [HTTP and Statuses](reference/api.en.md#s10-2) |
| Fonts, title layouts, presets | [Style Configurations](reference/editing.en.md#s7), [Module Handover](reference/api.en.md#s10-6) |
| Frontend and backend not yet integrated | [Stand-alone Development Mocks](reference/api.en.md#s10-5), [Runnable Tools](../contracts/collaboration/README.en.md) |

## Process for Modifying Contracts

A maintains public contracts and B proposes requirements; first demonstrate the differences between old and new fields/signatures and coordinate callers on both sides, then update definitions, examples, mocks, and implementations in a single complete change. Bump corresponding versions when meanings change. Conflicts must not rely on callers guessing compatibility; record specific inconsistencies first and explicitly correct them.

The original competition examples and development mocks are simulated data; Vlogii already has implementations/records for real API, AI, rendering, and local recovery, but has not implemented the old contracts here or completed Replit acceptance. See [Tool Descriptions](../contracts/collaboration/README.en.md) for commands and scope for running checks.
