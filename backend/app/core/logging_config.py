"""
구조화 로깅 설정

setup_logging()을 호출하면 stdlib root logger를 structlog 포매터로 래핑.
기존 코드의 logging.getLogger() 호출을 수정 없이 구조화 로그로 전환.
"""

import logging
import sys

import structlog


def setup_logging(env: str = "development") -> None:
    """structlog + stdlib 통합 설정"""

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if env == "production":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    # 노이즈가 심한 라이브러리 로거 레벨 조정
    for noisy in ("uvicorn.access", "httpx", "httpcore", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
