def get_create_log_config(debug: bool, loglevel: str):
    if debug:
        logformat = "%(asctime)s|%(levelname)-8s| %(module)-30s:%(lineno)-4d| %(message)s"
    else:
        logformat = "%(asctime)s|%(levelname)-8s| %(message)s"

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": logformat,
                "datefmt": "%H:%M:%S",
            },
        },
        "handlers": {
            "null": {
                "class": "logging.NullHandler",
            },
            "console": {
                "level": "NOTSET",
                "formatter": "standard",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
            "stderr": {
                "level": "ERROR",
                "formatter": "standard",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
        },
        "loggers": {
            "": {  # root logger
                "level": "WARNING",
                "handlers": ["console", "stderr"],
            },
            "__main__": {
                "level": "DEBUG",
            },
            "scripts": {
                "level": loglevel,
            },
            "gw2_logs": {
                "level": loglevel,
            },
        },
    }
