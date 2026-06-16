def test_create_and_poll_task(client):
    create_response = client.post(
        "/api/tasks",
        json={"projectId": "project-1", "stage": "uploading", "message": "Queued"},
    )

    assert create_response.status_code == 201
    created = create_response.json()

    poll_response = client.get(f"/api/tasks/{created['taskId']}")

    assert poll_response.status_code == 200
    assert poll_response.json()["taskId"] == created["taskId"]


def test_retry_failed_task(client):
    created = client.post(
        "/api/tasks",
        json={"projectId": "project-1", "stage": "uploading", "message": "Queued"},
    ).json()
    client.post(
        f"/api/tasks/{created['taskId']}/events",
        json={
            "status": "failed",
            "stage": "extracting_metadata",
            "progress": 10,
            "message": "Failed",
            "error": {"code": "tool_failed", "message": "boom", "retryable": True},
        },
    )

    response = client.post(f"/api/tasks/{created['taskId']}/retry")

    assert response.status_code == 400
    assert "No sample or generation" in response.json()["detail"]


def test_cancel_running_task(client):
    created = client.post(
        "/api/tasks",
        json={"projectId": "project-1", "stage": "uploading", "message": "Queued"},
    ).json()

    response = client.post(f"/api/tasks/{created['taskId']}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_sse_stream_returns_task_events(client):
    created = client.post(
        "/api/tasks",
        json={"projectId": "project-1", "stage": "uploading", "message": "Queued"},
    ).json()

    with client.stream("GET", f"/api/tasks/{created['taskId']}/events?once=true") as response:
        body = response.read().decode("utf-8")

    assert response.status_code == 200
    assert "event: task" in body
    assert f'"taskId":"{created["taskId"]}"' in body
    assert '"eventId":' in body
    assert ": close" in body


def test_sse_stream_after_id_returns_incremental_events(client):
    created = client.post(
        "/api/tasks",
        json={"projectId": "project-1", "stage": "uploading", "message": "Queued"},
    ).json()
    task_id = created["taskId"]

    with client.stream("GET", f"/api/tasks/{task_id}/events?once=true") as response:
        first_body = response.read().decode("utf-8")

    assert "event: task" in first_body
    import json as json_module

    data_line = next(line for line in first_body.splitlines() if line.startswith("data: "))
    first_event = json_module.loads(data_line.removeprefix("data: "))
    first_id = first_event["eventId"]

    client.post(
        f"/api/tasks/{task_id}/events",
        json={
            "status": "running",
            "stage": "extracting_metadata",
            "progress": 25,
            "message": "Running",
        },
    )

    with client.stream(
        "GET",
        f"/api/tasks/{task_id}/events?once=true&after_id={first_id}",
    ) as response:
        second_body = response.read().decode("utf-8")

    assert "Running" in second_body
    assert "Queued" not in second_body
