import logging

from rich.console import Console
from rich.logging import RichHandler

console = Console()
logger = logging.getLogger("agent_sync")


def configure_logging(level: int = logging.INFO) -> None:
    """Attach a Rich log handler once so library output stays consistent."""

    if logger.handlers:
        return

    handler = RichHandler(console=console, show_time=False, show_path=False, markup=True)
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
