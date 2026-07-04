from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def log_evaluation_failure(scope: str, *, project_id: str, entity_id: str, exc: Exception) -> None:
    logger.exception(
        "evaluation_write_failed scope=%s project_id=%s entity_id=%s error=%s",
        scope,
        project_id,
        entity_id,
        exc,
    )
