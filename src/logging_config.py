"""Per-component debug logs; communication.log is JSON Lines."""
import json
import logging
import os
from pathlib import Path
import re

_secrets = ()


def refresh_redaction():
    global _secrets
    _secrets = tuple(value for name, value in os.environ.items()
                     if any(word in name.upper() for word in ("KEY", "TOKEN", "SECRET", "PASSWORD")) and len(value) > 6)


def redact(text):
    for value in _secrets:
        text = text.replace(value, "[REDACTED]")
    return re.sub(r"(?<![A-Za-z0-9_])sk-[A-Za-z0-9_-]+", "[REDACTED]", text)


class SafeFormatter(logging.Formatter):
    def format(self, record):
        return redact(super().format(record))


class CommunicationFormatter(logging.Formatter):
    def format(self, record):
        value = json.loads(record.getMessage())
        def clean(item):
            if isinstance(item, str):
                return redact(item)
            if isinstance(item, list):
                return [clean(entry) for entry in item]
            if isinstance(item, dict):
                return {key: ("[REDACTED]" if any(word in key.lower() for word in ("api_key", "password", "secret", "token")) else clean(entry)) for key, entry in item.items()}
            return item
        return json.dumps(clean(value), ensure_ascii=False)


def configure_logging(log_dir="logs", level=logging.DEBUG):
    directory = Path(log_dir)
    refresh_redaction()
    directory.mkdir(parents=True, exist_ok=True)
    for name in ("coordinator", "communication", "data_agent", "code_agent", "evaluator_agent", "system",
                 "query_database", "python_repl", "create_file", "score_result"):
        logger = logging.getLogger(name)
        for handler in list(logger.handlers):
            if getattr(handler, "multi_agent_debug", False):
                logger.removeHandler(handler)
                handler.close()
        handler = logging.FileHandler(directory / f"{name}.log", encoding="utf-8")
        handler.multi_agent_debug = True
        handler.setFormatter(CommunicationFormatter() if name == "communication" else
                             SafeFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(level)
        logger.propagate = False
    return directory
