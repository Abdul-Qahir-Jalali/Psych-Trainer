"""
Central Logger Setup using `structlog`.

This module configures the standard library `logging` module to route all
events through `structlog`. In production environments, it outputs pure JSON.
In development environments, it formats logs via a colorizer for readability.
"""

import logging
import os
import sys

import structlog


def setup_logger():
    """Idempotent function to configure Structlog globally."""
    
    # 1. Determine environment (default to DEV colors if not explicitly PROD)
    is_prod = os.environ.get("ENVIRONMENT", "dev").lower() in ("prod", "production")

    # 2. Define shared processors that run on every log line (e.g. timestamps)
    shared_processors = [
        structlog.contextvars.merge_contextvars,          # Allows injecting thread-local request IDs
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,             # Unpacks exceptions
    ]

    # 3. Choose the final formatter (JSON vs Colored Console)
    if is_prod:
        formatter = structlog.processors.JSONRenderer()
    else:
        formatter = structlog.dev.ConsoleRenderer(colors=True)

    # 4. Bind the Structlog configuration
    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # 5. Intercept Standard Library Python Logging
    formatter_processor = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            formatter,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter_processor)
    
    # Replace the default handlers on the root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    
    # Optional: Suppress ultra-verbose third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.INFO)

    root_logger.setLevel(logging.INFO)
