from dataclasses import dataclass, asdict

@dataclass
class HealthReport:
    run_id: str
    health: str
    assets_processed: int
    documents_found: int
    critical_count: int
    warning_count: int
    error_count: int
    execution_time_seconds: float

    def to_dict(self) -> dict:
        return asdict(self)
