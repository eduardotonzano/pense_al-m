import json
import logging
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path


SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
    "api_key",
    "access_token",
    "refresh_token",
}


def sanitize_value(value):
    """Converte valores para JSON e oculta informacoes sensiveis."""

    if isinstance(value, dict):
        return {
            str(key): (
                "[REDACTED]"
                if str(key).strip().casefold() in SENSITIVE_KEYS
                else sanitize_value(item)
            )
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [sanitize_value(item) for item in value]

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, Decimal):
        return format(value, "f")

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, BaseException):
        return {
            "error_type": type(value).__name__,
            "error_message": str(value),
        }

    return value


class JsonLinesFormatter(logging.Formatter):
    """Formata cada registro como um objeto JSON independente."""

    RESERVED = set(logging.makeLogRecord({}).__dict__) | {
        "message",
        "asctime",
    }

    def format(self, record):
        data = {
            "timestamp": datetime.fromtimestamp(
                record.created
            ).astimezone().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key not in self.RESERVED and not key.startswith("_"):
                data[key] = sanitize_value(value)

        if record.exc_info:
            error = record.exc_info[1]
            data["error_type"] = type(error).__name__
            data["error_message"] = str(error)

        return json.dumps(
            sanitize_value(data),
            ensure_ascii=False,
            separators=(",", ":"),
        )


def configure_operational_logging(
    log_dir="logs",
    level=logging.INFO,
    logger_name="debenture_search.operation",
):
    """Configura arquivos de log textual e JSONL sem duplicar handlers."""

    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)

    text_path = directory / "debenture_collection.log"
    jsonl_path = directory / "debenture_collection.jsonl"

    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    logger.propagate = False

    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)

    text_handler = logging.FileHandler(
        text_path,
        encoding="utf-8",
    )
    text_handler.setLevel(level)
    text_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    json_handler = logging.FileHandler(
        jsonl_path,
        encoding="utf-8",
    )
    json_handler.setLevel(level)
    json_handler.setFormatter(JsonLinesFormatter())

    logger.addHandler(text_handler)
    logger.addHandler(json_handler)

    return {
        "logger": logger,
        "text_path": text_path,
        "jsonl_path": jsonl_path,
    }


def close_operational_logging(logger):
    """Libera os arquivos de log para copia, rotacao ou exclusao."""

    for handler in list(logger.handlers):
        handler.flush()
        handler.close()
        logger.removeHandler(handler)
