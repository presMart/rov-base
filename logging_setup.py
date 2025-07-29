import json, logging.config, pathlib, copy
from functools import lru_cache

_DEFAULT = {
    "version": 1,
    "formatters": {
        "plain": {"format": "%(asctime)s [%(levelname)s] %(name)s - %(message)s"}
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "plain",
            "level": "INFO",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "rov.log",
            "maxBytes": 500_000,
            "backupCount": 5,
            "formatter": "plain",
            "level": "INFO",
        },
    },
    "root": {"handlers": ["console", "file"], "level": "INFO"},
}

@lru_cache(maxsize=1)
def setup_logging(cfg_path: str | None = "log_config.json",
                  *,                                   # force kw-only overrides
                  logfile: str | None = None,
                  console_level: str | None = None):
    """Configure logging once per process.

    - If *cfg_path* exists, merge it over the defaults.
    - Optional kwargs let each entry-point tweak small bits
      without maintaining two huge dicts.
    """
    config = copy.deepcopy(_DEFAULT)
    if pathlib.Path(cfg_path).exists():
        user = json.loads(pathlib.Path(cfg_path).read_text())
        config.update(user)

    if logfile:
        config["handlers"]["file"]["filename"] = logfile
    if console_level:
        config["handlers"]["console"]["level"] = console_level

    logging.config.dictConfig(config)