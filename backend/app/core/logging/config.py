"""日志统一配置。

- 开发（DEBUG_MODE=True）：彩色文本，给人眼读。
- 生产（DEBUG_MODE=False）：JSON 行，给日志收集系统（ELK / Loki / Datadog）解析。

应用启动时调用 `setup_logging()` 一次，之后各模块照常 `logger = logging.getLogger(__name__)`，
日志会自动经过 RequestIDFilter 附上 request_id 字段。
"""

import logging.config
from typing import Any

from app.core.config import settings


def _build_config(debug: bool) -> dict[str, Any]:
    formatter_key = "color" if debug else "json"

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "request_id": {
                "()": "app.core.logging.filters.RequestIDFilter",
            },
        },
        "formatters": {
            "color": {
                "()": "colorlog.ColoredFormatter",
                "format": (
                    "%(log_color)s%(asctime)s | %(levelname)-8s | "
                    "%(name)s:%(lineno)d | [req-%(request_id)s] %(message)s"
                ),
                "datefmt": "%Y-%m-%d %H:%M:%S",
                "log_colors": {
                    "DEBUG": "cyan",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "red,bg_white",
                },
            },
            "json": {
                "()": "pythonjsonlogger.json.JsonFormatter",
                # fmt 决定哪些 LogRecord 标准属性进 JSON；extra={...} 字段自动展开
                "fmt": "%(asctime)s %(levelname)s %(name)s %(lineno)d %(request_id)s %(message)s",
                "datefmt": "%Y-%m-%dT%H:%M:%S%z",
                "rename_fields": {
                    "asctime": "timestamp",
                    "levelname": "level",
                    "name": "logger",
                    "lineno": "line",
                },
            },
        },
        "handlers": {
            "stdout": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": formatter_key,
                "filters": ["request_id"],
            },
        },
        "loggers": {
            # 项目自己的日志
            "app": {
                "level": "DEBUG" if debug else "INFO",
                "handlers": ["stdout"],
                "propagate": False,
            },
            # 接管 uvicorn 三个 logger，统一走我们的格式
            "uvicorn": {"level": "INFO", "handlers": ["stdout"], "propagate": False},
            "uvicorn.error": {"level": "INFO", "handlers": ["stdout"], "propagate": False},
            "uvicorn.access": {"level": "INFO", "handlers": ["stdout"], "propagate": False},
            # 压低吵闹的第三方
            "tortoise": {"level": "WARNING"},
            "tortoise.db_client": {"level": "WARNING"},
            "asyncpg": {"level": "WARNING"},
            "urllib3": {"level": "WARNING"},
            "httpx": {"level": "WARNING"},
            "boto3": {"level": "WARNING"},
            "botocore": {"level": "WARNING"},
            "s3transfer": {"level": "WARNING"},
            "watchfiles": {"level": "WARNING"},
        },
        # 兜底：未明确声明的 logger 走这里
        "root": {
            "level": "INFO",
            "handlers": ["stdout"],
        },
    }


def setup_logging() -> None:
    """应用启动时调用一次。后续模块只需 `logger = logging.getLogger(__name__)`。"""
    logging.config.dictConfig(_build_config(debug=settings.DEBUG_MODE))
