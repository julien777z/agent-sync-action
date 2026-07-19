import logging

logger = logging.getLogger(__name__)


class AgentSyncError(ValueError):
    """Report invalid canonical input or an unsafe generated state."""
