import sqlite3


def test_create_app_initializes_sqlite_schema(app_paths):
    from app.main import create_app

    create_app(
        database_path=app_paths["database_path"],
        storage_root=app_paths["storage_root"],
    )

    with sqlite3.connect(app_paths["database_path"]) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert {"projects", "tasks", "artifacts", "task_events"}.issubset(table_names)


def test_health_endpoint_reports_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
