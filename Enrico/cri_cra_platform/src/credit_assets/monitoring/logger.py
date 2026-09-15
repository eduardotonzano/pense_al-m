import logging
from pathlib import Path

def configure_logging(log_dir: str = "logs", level: str = "INFO") -> None:
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=getattr(logging, level.upper()), format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", handlers=[logging.FileHandler(Path(log_dir)/"platform.log", encoding="utf-8"), logging.StreamHandler()])
