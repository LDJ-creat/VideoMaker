# HyperFrames Agent Composition E2E Checklist

## Prerequisites

- Node.js >= 22, FFmpeg on PATH
- Repo root: `npm install` + `npm run hyperframes:doctor`
- `skills/public/hyperframes/SKILL.md` present
- `skills/private/videomaker-composition/SKILL.md` present
- Worker env: `VIDEOMAKER_COMPOSITION_MODE=hybrid` (default)

## Unit / module

```powershell
cd packages/contracts
npm run check
npm run validate:schemas

cd services/composition
python -m pytest

cd services/worker
python -m pytest tests/test_hyperframes_material_tool.py tests/test_hyperframes_material_provider.py -q
```

## Skill bootstrap

1. Set `VIDEOMAKER_COMPOSITION_AGENT_MODE=single_shot` for deterministic LLM JSON path.
2. Run material author on a packaging slot (`benefit_card`).
3. Confirm agent system prompt contains `<available_skills>` and `<skill_usage_rule>`.

## Composition template render

1. Set `VIDEOMAKER_COMPOSITION_AGENT_MODE=react` with text provider configured.
2. Trigger generation with a slot using `hyperframes_material`.
3. Verify `generated/{actionId}/composition/index.html` exists.
4. Verify output MP4 artifact registered.

## Pattern deposit / promote

1. Complete a successful HF material render (lint + MP4).
2. Confirm draft at `storage/projects/{projectId}/knowledge/drafts/composition/{generationId}/{slotId}/`.
3. `POST /api/projects/{projectId}/knowledge/composition/promote` with `userScore>=4`, `confirm=true`.
4. Verify published entry under `storage/knowledge/{categorySlug}/{entryId}/` with `composition-skill.md` + `spec.template.json`.
5. SQLite `knowledge_entries.entry_kind = composition_pattern`.

## Regression

- Legacy templates (`benefit-card`, `ken-burns`) still render with `VIDEOMAKER_COMPOSITION_MODE=legacy`.
- HyperFrames preview fallback unchanged when packaging text effects require HF CLI.
