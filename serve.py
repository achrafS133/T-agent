"""Start the T-AGENT PRO API server."""

from __future__ import annotations

import uvicorn

from src.config import config
from src.logging_config import setup_logging


def main() -> None:
    setup_logging()
    uvicorn.run(
        "src.api:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
