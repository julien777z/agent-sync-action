import logging

logger = logging.getLogger("agent_sync")


def configure_logging(level: int = logging.INFO) -> None:
    """Attach a stream log handler to the agent_sync logger once."""

    if logger.handlers:
        return

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
