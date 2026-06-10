from __future__ import annotations


def test_generation_pipeline_exposes_finish_reconcile_helper() -> None:
    from app.pipelines import generation_pipeline

    assert callable(generation_pipeline.reconcile_gap_finish_from_storyboard)
