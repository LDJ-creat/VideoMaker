# API Task Artifacts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI P0 backend foundation for projects, long-running task state, artifact records, polling, retry/cancel, and SSE progress events.

**Architecture:** The API uses SQLite as the authoritative state store and local filesystem paths as artifact references. Task updates are persisted to `tasks`, `task_events`, and `artifacts`; the SSE endpoint streams persisted events and falls back cleanly to the polling endpoint.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, SQLite, pytest, httpx.

---

### Task 1: API Skeleton And Database Session

**Files:**
- Create: `services/api/pyproject.toml`
- Create: `services/api/app/__init__.py`
- Create: `services/api/app/main.py`
- Create: `services/api/app/settings.py`
- Create: `services/api/app/db/__init__.py`
- Create: `services/api/app/db/schema.sql`
- Create: `services/api/app/db/session.py`
- Create: `services/api/tests/conftest.py`

- [x] Write failing tests for app creation and schema initialization.
- [x] Implement settings, SQLite schema bootstrap, and FastAPI app factory.
- [x] Verify tests pass.

### Task 2: Task Event Service

**Files:**
- Create: `services/api/app/services/task_events.py`
- Create: `services/api/tests/test_task_events.py`

- [x] Write failing tests for task creation, event persistence, task update, terminal status detection, and recent event listing.
- [x] Implement `TaskEventService`.
- [x] Verify tests pass.

### Task 3: Artifact Store

**Files:**
- Create: `services/api/app/services/artifact_store.py`
- Create: `services/api/tests/test_artifact_store.py`

- [x] Write failing tests for project-scoped path resolution, artifact registration, and path traversal rejection.
- [x] Implement `ArtifactStore`.
- [x] Verify tests pass.

### Task 4: Task API Routes

**Files:**
- Create: `services/api/app/routers/__init__.py`
- Create: `services/api/app/routers/tasks.py`
- Modify: `services/api/app/main.py`
- Create: `services/api/tests/test_task_routes.py`

- [x] Write failing tests for creating tasks, polling latest task state, retry, cancel, and SSE event stream.
- [x] Implement task routes.
- [x] Verify tests pass.

### Task 5: Verification And Commit

**Files:**
- Modify: `docs/superpowers/plans/2026-05-27-api-task-artifacts-plan.md`

- [x] Run `python -m pytest`.
- [x] Run `python -m compileall app`.
- [x] Commit the API task/artifact implementation.
