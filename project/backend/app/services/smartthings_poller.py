import logging

logger = logging.getLogger(__name__)


async def poll_loop() -> None:
    """SmartThings 서버 polling 비활성 — GitHub Actions 릴레이가 대체."""
    logger.info("SmartThings 서버 polling 비활성 — GitHub Actions 릴레이 사용 중")
