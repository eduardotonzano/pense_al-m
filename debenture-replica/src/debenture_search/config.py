import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CollectionConfig:
    asset_codes: tuple
    request_timeout_seconds: float = 20.0
    request_interval_seconds: float = 2.0
    max_items: int = 20
    max_attempts: int = 1
    stale_run_minutes: int = 60
    create_backup: bool = True
    export_csv: bool = True
    export_json: bool = True
    export_history: bool = True
    export_dir: str = "exports"

    @staticmethod
    def _positive_number(value, field_name, allow_zero=False):
        number = float(value)
        minimum_ok = number >= 0 if allow_zero else number > 0
        if not minimum_ok:
            raise ValueError(field_name + " possui valor invalido.")
        return number

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ValueError("A configuracao deve ser um objeto JSON.")

        raw_codes = data.get("asset_codes")
        if not isinstance(raw_codes, list):
            raise ValueError("asset_codes deve ser uma lista.")

        codes = []
        seen = set()
        for value in raw_codes:
            code = "".join(str(value or "").strip().upper().split())
            if code and code not in seen:
                seen.add(code)
                codes.append(code)

        if not codes:
            raise ValueError("asset_codes nao possui codigos validos.")

        max_items = int(data.get("max_items", 20))
        if max_items < 1:
            raise ValueError("max_items deve ser maior que zero.")
        if len(codes) > max_items:
            raise ValueError("asset_codes excede max_items.")

        max_attempts = int(data.get("max_attempts", 1))
        if max_attempts < 1 or max_attempts > 3:
            raise ValueError("max_attempts deve ficar entre 1 e 3.")

        stale_minutes = int(data.get("stale_run_minutes", 60))
        if stale_minutes < 1:
            raise ValueError("stale_run_minutes deve ser maior que zero.")

        export_dir = str(data.get("export_dir", "exports")).strip()
        if not export_dir:
            raise ValueError("export_dir nao pode ficar vazio.")

        return cls(
            asset_codes=tuple(codes),
            request_timeout_seconds=cls._positive_number(
                data.get("request_timeout_seconds", 20),
                "request_timeout_seconds",
            ),
            request_interval_seconds=cls._positive_number(
                data.get("request_interval_seconds", 2),
                "request_interval_seconds",
                allow_zero=True,
            ),
            max_items=max_items,
            max_attempts=max_attempts,
            stale_run_minutes=stale_minutes,
            create_backup=bool(data.get("create_backup", True)),
            export_csv=bool(data.get("export_csv", True)),
            export_json=bool(data.get("export_json", True)),
            export_history=bool(data.get("export_history", True)),
            export_dir=export_dir,
        )


def load_collection_config(path):
    candidate = Path(path)
    if not candidate.exists():
        raise ValueError("Arquivo de configuracao nao encontrado.")

    try:
        data = json.loads(candidate.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        raise ValueError("O arquivo de configuracao possui JSON invalido.") from error

    return CollectionConfig.from_dict(data)
