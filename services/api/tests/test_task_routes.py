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
