from app.services.task_events import TaskEventService


def test_create_task_persists_initial_event(app):
    service = TaskEventService(app.state.db)

    event = service.create_task(project_id="project-1", stage="uploading", message="Queued")

    assert event["taskId"]
    assert event["status"] == "queued"
    assert event["stage"] == "uploading"
    assert event["progress"] == 0

    stored = service.get_task(event["taskId"])
    events = service.list_events(event["taskId"])

    assert stored == event
    assert events == [event]


def test_update_task_appends_event_and_artifacts(app):
    service = TaskEventService(app.state.db)
    created = service.create_task(project_id="project-1", stage="uploading", message="Queued")

    updated = service.update_task(
        created["taskId"],
        status="running",
        stage="extracting_metadata",
        progress=10,
        message="Extracted metadata",
        artifact_refs=[
            {
                "id": "artifact-1",
                "type": "json",
                "uri": "storage/projects/project-1/artifacts/metadata.json",
                "createdAt": "2026-05-27T00:00:00Z",
            }
        ],
    )

    assert updated["status"] == "running"
    assert updated["artifactRefs"][0]["id"] == "artifact-1"
    assert len(service.list_events(created["taskId"])) == 2


def test_terminal_status_detection(app):
    service = TaskEventService(app.state.db)

    assert service.is_terminal("succeeded")
    assert service.is_terminal("failed")
    assert service.is_terminal("cancelled")
    assert not service.is_terminal("running")
