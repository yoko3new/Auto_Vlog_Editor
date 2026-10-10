# Which Documents Need to Be Retained Permanently

[中文](maintenance.md) · **English**

[Back to Overview](../README.en.md). The team's shared current documents and contracts are stored in the same Git repository alongside the code; personal development configurations remain local. **Retention does not mean reading every time, nor does it mean updating every round.**

## The Three Documents You Focus on Regularly

| File | Purpose | When to Update |
| --- | --- | --- |
| [README](../README.en.md) | Project introduction and entry navigation | When the product overview, entry points, or actual startup methods change |
| [Collaboration Handbook](collaboration.en.md) | Who is responsible for what, when to hand off, how to avoid waiting | When the division of labor, interface handoffs, or milestones change |
| [Current Progress](status.en.md) | Completed, blocked, what to do next | Summarized and updated by A when there is actual progress or a decision is needed |

Important product/technical decisions you make should also be saved to [decisions.md](decisions.en.md); agents will use this to avoid repeated discussions and reverting to old solutions.

## Contents Retained in the Repository Long-Term

| Content | Why Retained | Primary Maintainer |
| --- | --- | --- |
| [AGENTS.md](../AGENTS.en.md) | Brief rules and reading routing for agents | A |
| [Product Definition](product.en.md), [MVP Comparison](mvp-coverage.en.md) | Competition goals, current implementation, and gaps | Both confirm scope, maintained by A |
| [Architecture](architecture.en.md), [Contract Navigation](contracts.en.md), [Technical Reference](reference/) | Prevent modules and fields from evolving independently | A; jointly verify boundaries involving B |
| [contracts/](../contracts/) | Machine-verifiable schemas, samples, APIs, and development stubs | A; public changes synchronized on both sides |
| [Visual Specifications](visual-design.en.md) | Unified style for pages and final videos | B manages pages, A manages video titles/final videos; jointly verified |
| [Acceptance](acceptance.en.md), [Deployment](deployment.en.md), [AI Testing](ai-selection.en.md) | Clarify what counts as demonstrable, real, and valid | Module leads provide evidence, A updates status |
| [Decision Log](decisions.en.md), [Schedule](status.en.md) | Resume work across sessions and computers | Unified maintenance by A |
| [Demo Preparation](demo.en.md) | Asset licensing, screen recording, submission, and rehearsal | A/B |

What must be retained in the shared repository are the team's current documents and contracts; you only need to frequently focus on the three documents above and matters requiring your decisions. Documents must be committed and synchronized together with the code, not left only in some chat attachment.

## Archived and Temporary Materials

- `docs/archive/`: Old long documents are kept locally only for backtracking, ignored, not uploaded to GitHub.
- `agent-roles/`, `docs/agent-workflow.md`, `.codex/`, `.agents/`, `LOCAL-DEVELOPMENT.md`: Roles/scheduling/settings for personal coding assistants remain local. Teammates do not need to install the same configuration.
- `AGENTS.md`: The name contains agent, but the content consists of team-shared specifications and document navigation, which should be synchronized with the repository and does not contain personal model or scheduling settings.
- `work/`: Drafts, migration scripts, temporary logs, and caches; can be cleaned up after confirming important conclusions are saved, not to be used as the sole basis for acceptance.
- `outputs/`: Shareable documentation package and instructions for this iteration; merely a snapshot, subsequent work relies on the repository's current files to avoid overwriting new code with old archives.
- Original assets, generated MP4s, private annotations, and keys: Retained in agreed local/cloud locations; Git preserves necessary inventories, hashes, licenses, and non-sensitive evidence, without directly uploading private assets or keys.

## Documentation Synchronization Conventions

Each requirement is defined in detail in only one place, while other documents provide summaries and links. Fields use schema/OpenAPI as structural basis, cross-field semantics are based on corresponding technical references, and phase scopes are based on product definitions; when conflicts are found, clarify and correct first rather than deleting requirements on your own.

Update associated documents whenever modifying behavior; update progress upon completion/blocking; record decisions when altering confirmed directions. Preserve actual commands, results, baselines, and unverified items before finishing tasks, without needing to copy the full chat text into the repository.

Shared Markdown documents have complete Chinese and English versions, with a language switch at the top and navigation in the selected language. Existing paths are preserved; the counterpart uses `.en.md` or `.zh.md` in the same directory. Keep both versions synchronized when rules or feature descriptions change, and preserve matching stable anchors. Do not translate code, field names, commands or code blocks. Run `python3 tools/check_docs.py` to check pairs, language switches, anchors, code blocks and links. Personal notes and original license texts are excluded from translation.
