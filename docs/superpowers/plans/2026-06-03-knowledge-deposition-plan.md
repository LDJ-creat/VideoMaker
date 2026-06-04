# Knowledge Deposition Implementation Plan

> **Status:** Implemented 2026-06-03. Karpathy-style Markdown Skill wiki + SQLite index + auto-recommend/bind.

**Goal:** After sample analysis, generate readable structure skills via `knowledge_author`, store drafts under the project, promote to a global library, auto-recommend and bind knowledge for new briefs, and inject progressive disclosure context into generation Agents.

**Architecture:** `VideoStructure` JSON remains authoritative. Markdown skills are the human-readable layer. SQLite stores index fields and per-project selection; file bodies live under `storage/`.

---

## Storage Layout

```text
storage/
├── global/cookies/                         # existing
├── projects/{projectId}/
│   └── knowledge/drafts/{sampleId}/
│       ├── structure-skill.md
│       ├── video-structure.json
│       └── entry-meta.json
└── knowledge/{categorySlug}/{entryId}/     # published global library
    ├── structure-skill.md
    ├── video-structure.json
    └── entry-meta.json
```

---

## Contracts

- `KnowledgeEntry`, `KnowledgeRecommendation`, `ProjectKnowledgeSelection` in `packages/contracts`
- Task stage: `rendering_knowledge_draft`

---

## Worker

| Module | Role |
|--------|------|
| `knowledge_author` Agent | LLM generates skill MD from `VideoStructure` |
| `deposit.py` | Draft write after structure extraction |
| `context_resolver.py` | L1/L2 progressive disclosure for generation |
| `knowledge_selector` Agent | Optional LLM rerank (live mode only) |

Pipeline hook: `p0_demo_pipeline.analyze_sample` → `rendering_knowledge_draft` (soft-fail).

Generation: `resolve_knowledge_context` before slot mapping; weak slots ≥2 upgrade to L2 full skill.

---

## API

**Tables:** `knowledge_entries`, `project_knowledge_selection`

**Services:** `KnowledgeStore`, `KnowledgeRecommender`

**Routes:**

| Method | Path |
|--------|------|
| GET | `/api/knowledge/entries` |
| GET | `/api/knowledge/entries/{id}` |
| GET | `/api/knowledge/entries/{id}/skill` |
| GET | `/api/projects/{id}/samples/{sampleId}/knowledge-draft` |
| POST | `/api/projects/{id}/samples/{sampleId}/knowledge/promote` |
| POST | `/api/projects/{id}/knowledge/recommend` |
| GET/PUT | `/api/projects/{id}/knowledge/selection` |
| POST | `/api/projects/{id}/knowledge/selection/reset` |
| POST | `/api/projects/{id}/structure-from-knowledge` |

**Auto-bind triggers:**

1. `POST .../brief` → `ensure_selection`
2. `POST .../generation-plan` → `ensure_selection` then dispatch

When no analyzed real sample exists, Top-1 knowledge entry is applied as `source_kind=knowledge` sample.

---

## Frontend

- `KnowledgeDraftPanel` — draft preview + promote
- `KnowledgeSelectionPanel` — auto-selected entry + override
- `KnowledgeLibraryView` — browse published entries
- Workbench tab: **知识库**

---

## Recommendation Algorithm (v1)

**Stage A:** Structured scoring (category/tone/slotPattern overlap) — always.

**Stage B:** `knowledge_selector` LLM rerank when not in fixture mode and ModelGateway available.

**Stage C:** Auto-bind Top-1 + references #2–#3.

---

## Progressive Disclosure

| Level | Content |
|-------|---------|
| L0 | Index cards (title, summary, slotPattern) |
| L1 | Parsed MD sections (default) |
| L2 | Full `structure-skill.md` when weak slots ≥2 |

---

## Verification

```powershell
cd packages/contracts && npm run check && npm run validate:schemas
cd services/shared && python -m pytest tests/test_knowledge_*.py
cd services/worker && python -m pytest tests/test_knowledge_*.py
cd services/api && python -m pytest tests/test_knowledge_routes.py
cd apps/web && npm run typecheck && npm run test
```

---

## Deferred

- Vector embedding retrieval
- Knowledge merge/fork evolution
- Automatic version archiving under `versions/v{n}/`
