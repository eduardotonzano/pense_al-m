from debenture_search.services.health_monitor_service import (
    HealthMonitorService,
)


def test_health_monitor_integration(tmp_path):

    logs = tmp_path / "logs"
    runtime = tmp_path / "runtime"

    logs.mkdir()
    runtime.mkdir()

    (logs / "collection_last.json").write_text(
        """
        {
            "status":"success"
        }
        """,
        encoding="utf-8",
    )

    (logs / "quality_last.json").write_text(
        """
        {
            "status":"success",
            "critical_count":0,
            "warning_count":0
        }
        """,
        encoding="utf-8",
    )

    report = HealthMonitorService(
        logs_directory=logs,
        runtime_directory=runtime,
    ).save_report()

    assert report.health == "healthy"
    assert report.critical_count == 0
