from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.services.knowledge_recommender import KnowledgeRecommender
from app.services.knowledge_store import KnowledgeStore
from app.services.project_store import ProjectStore

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class PromoteKnowledgeRequest(BaseModel):
    title: str = ""
    category: str = ""
    style: str = ""
    hook_type: str | None = Field(default=None, alias="hookType")
    summary_override: str | None = Field(default=None, alias="summaryOverride")
    category_slug: str | None = Field(default=None, alias="categorySlug")

    model_config = {"populate_by_name": True}


class ApplyKnowledgeRequest(BaseModel):
    entry_id: str = Field(alias="entryId")
    apply_structure: bool = Field(default=True, alias="applyStructure")

    model_config = {"populate_by_name": True}


class UpdateSelectionRequest(BaseModel):
    primary_entry_id: str | None = Field(default=None, alias="primaryEntryId")
    reference_entry_ids: list[str] = Field(default_factory=list, alias="referenceEntryIds")
    apply_structure: bool = Field(default=False, alias="applyStructure")

    model_config = {"populate_by_name": True}


def _knowledge_store(request: Request) -> KnowledgeStore:
    return KnowledgeStore(request.app.state.db, request.app.state.storage_root)


def _project_store(request: Request) -> ProjectStore:
    return ProjectStore(request.app.state.db)


def _recommender(request: Request) -> KnowledgeRecommender:
    return KnowledgeRecommender(
        _knowledge_store(request),
        _project_store(request),
        storage_root=request.app.state.storage_root,
        database_path=request.app.state.db.path,
    )


@router.get("/entries")
def list_knowledge_entries(
    request: Request,
    category: str | None = None,
    style: str | None = None,
    hookType: str | None = None,
    tempo: str | None = None,
    q: str | None = None,
    status: str = "published",
) -> dict[str, Any]:
    entries = _knowledge_store(request).list_entries(
        status=status,
        category=category,
        style=style,
        hook_type=hookType,
        tempo=tempo,
        query=q,
    )
    return {"entries": entries}


@router.get("/entries/{entry_id}")
def get_knowledge_entry(entry_id: str, request: Request) -> dict[str, Any]:
    entry = _knowledge_store(request).get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    return entry


@router.get("/entries/{entry_id}/skill")
def get_knowledge_skill(entry_id: str, request: Request) -> dict[str, str]:
    markdown = _knowledge_store(request).read_skill_md(entry_id)
    if markdown is None:
        raise HTTPException(status_code=404, detail="Knowledge skill not found")
    return {"entryId": entry_id, "markdown": markdown}


project_router = APIRouter(prefix="/api/projects", tags=["projects-knowledge"])


@project_router.get("/{project_id}/samples/{sample_id}/knowledge-draft")
def get_knowledge_draft(project_id: str, sample_id: str, request: Request) -> dict[str, Any]:
    draft = _knowledge_store(request).get_draft(project_id, sample_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Knowledge draft not found")
    return draft


@project_router.post("/{project_id}/samples/{sample_id}/knowledge/promote")
def promote_knowledge_draft(
    project_id: str,
    sample_id: str,
    payload: PromoteKnowledgeRequest,
    request: Request,
) -> dict[str, Any]:
    if _project_store(request).get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        entry = _knowledge_store(request).promote_draft(
            project_id=project_id,
            sample_id=sample_id,
            title=payload.title,
            category=payload.category,
            style=payload.style,
            hook_type=payload.hook_type,
            summary_override=payload.summary_override,
            category_slug_override=payload.category_slug,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"entry": entry}


@project_router.post("/{project_id}/structure-from-knowledge")
def apply_structure_from_knowledge(
    project_id: str,
    payload: ApplyKnowledgeRequest,
    request: Request,
) -> dict[str, Any]:
    store = _project_store(request)
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    knowledge = _knowledge_store(request)
    try:
        if payload.apply_structure:
            applied = knowledge.apply_entry_to_project(
                project_id=project_id,
                entry_id=payload.entry_id,
                project_store=store,
            )
        else:
            applied = {"entryId": payload.entry_id}
        selection = _recommender(request).update_selection(
            project_id,
            primary_entry_id=payload.entry_id,
            apply_structure=payload.apply_structure,
        )
    except ValueError as exc:
        status_code = 400 if "reference only" in str(exc) else 404
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return {"applied": applied, "selection": selection}


@project_router.post("/{project_id}/knowledge/recommend")
def recommend_knowledge(project_id: str, request: Request) -> dict[str, Any]:
    if _project_store(request).get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    recommendation = _recommender(request).recommend(project_id)
    selection = _knowledge_store(request).get_selection(project_id)
    return {"recommendation": recommendation, "selection": selection}


@project_router.get("/{project_id}/knowledge/selection")
def get_knowledge_selection(project_id: str, request: Request) -> dict[str, Any]:
    if _project_store(request).get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    selection = _knowledge_store(request).get_selection(project_id)
    if selection is None:
        selection = _recommender(request).ensure_selection(project_id)
    return {"selection": selection}


@project_router.put("/{project_id}/knowledge/selection")
def update_knowledge_selection(
    project_id: str,
    payload: UpdateSelectionRequest,
    request: Request,
) -> dict[str, Any]:
    if _project_store(request).get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        selection = _recommender(request).update_selection(
            project_id,
            primary_entry_id=payload.primary_entry_id,
            reference_entry_ids=payload.reference_entry_ids,
            apply_structure=payload.apply_structure,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"selection": selection}


@project_router.post("/{project_id}/knowledge/selection/reset")
def reset_knowledge_selection(project_id: str, request: Request) -> dict[str, Any]:
    if _project_store(request).get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    selection = _recommender(request).reset_selection(project_id)
    return {"selection": selection}
