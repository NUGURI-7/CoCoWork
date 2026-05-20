"""日志 filter 集合。"""

import logging

from app.core.request_context import get_request_id


class RequestIDFilter(logging.Filter):
    """给每条 log record 附 `request_id` 属性，供 formatter 使用。

    无请求上下文时（lifespan 启动、CLI 脚本）会拿到默认值 '-'。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True
