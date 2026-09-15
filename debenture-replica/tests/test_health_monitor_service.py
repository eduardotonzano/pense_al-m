from debenture_search.services.health_monitor_service import (
    HealthMonitorService,
)


def test_health_report_creation(tmp_path):

    logs = tmp_path / "logs"
    runtime = tmp_path / "runtime"

    logs.mkdir()
    runtime.mkdir()

    (logs / "collection_last.json").write_text(
        '{"status":"success"}',
        encoding="utf-8",
    )

    (logs / "quality_last.json").write_text(
        """
        {
            "status":"success_with_warnings",
            "critical_count":0,
            "warning_count":2
        }
        """,
        encoding="utf-8",
    )

    report = HealthMonitorService(
        logs_directory=logs,
        runtime_directory=runtime,
    ).save_report()

    assert report.health == "warning"

    assert (
        logs / "health_last.json"
    ).exists()

    assert (
        logs / "health_history.jsonl"
    ).exists()