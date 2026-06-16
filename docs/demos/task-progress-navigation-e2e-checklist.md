# Task Progress Navigation E2E Checklist

Manual verification for SSE progress push and Workbench panel auto-navigation.

## Prerequisites

- API (`services/api/run-dev.ps1`) and web (`apps/web npm run dev`) running
- Model gateway configured for a full generation run (or fixture mode for smoke checks)

## Scenarios

### 1. Sample analysis completion

1. Upload a sample and start analysis from the workbench.
2. Confirm the UI switches to **进度** automatically.
3. Wait until progress reaches 100% / succeeded.
4. Confirm auto-navigation to **样例分析** with structure results loaded.

### 2. Generation — master script review gate

1. Start generation with human review enabled (default).
2. When master narration is ready, confirm auto-switch to **脚本审核**.
3. Approve master script.
4. Confirm return to **进度** and task status shows resuming (retrying/running).
5. Confirm progress updates continue without manual refresh.

### 3. Generation — storyboard review gate

1. Continue from scenario 2 through storyboard draft.
2. Confirm second auto-switch to **脚本审核** at storyboard gate.
3. Approve storyboard.
4. Confirm return to **进度** and material/render stages advance.

### 4. Dual-variant completion

1. Run generation with both `high_click` and `high_conversion`.
2. After both variants succeed, confirm auto-navigation to **结果**.
3. Confirm variant tabs and generation plans are hydrated.

### 5. Page refresh recovery

1. During `running` or `awaiting_review`, refresh the project page.
2. Confirm hydrate lands on **进度** or **脚本审核** as appropriate.
3. Confirm SSE/polling resumes and progress is not stale.

### 6. Manual tab override

1. During an active generation, manually open **结果** via the stepper.
2. Confirm pipeline does not steal focus while tasks still run.
3. Start a new analysis/generation run.
4. Confirm auto-navigation is re-enabled for the new run.

### 7. SSE fallback to polling

1. With devtools, block or drop `/api/tasks/*/events` requests.
2. After repeated SSE failures, confirm progress panel shows polling notice.
3. Confirm progress still updates via polling until terminal status.

### 8. Approve script — no bounce back to script-review

1. Reach **脚本审核** during generation (master or storyboard gate).
2. Approve and confirm immediate return to **进度**.
3. While the worker resumes, confirm the UI does **not** flash back to **脚本审核** when stale poll/SSE snapshots still say `awaiting_review`.
4. Confirm progress continues until the next review gate or completion.

### 9. Generation failure settlement

1. Start generation and force a variant task to `failed` (e.g. disable a required provider mid-run).
2. Confirm auto-navigation stays on **进度** (not **结果**).
3. Confirm failed task message is visible and retry works from the progress panel.

## Dev observability

In development builds, panel transitions log to the console as:

```text
[Workbench] panel progress -> script-review { reason, lastAction, autoNavEnabled }
```

Use this to diagnose missed navigation intents.
