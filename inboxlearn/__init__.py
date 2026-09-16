"""InboxLearn: a local, human-in-the-loop email classifier."""

from .config import CATEGORIES, PRIORITIES, Settings
from .service import InboxLearnService

__all__ = ["CATEGORIES", "PRIORITIES", "Settings", "InboxLearnService"]
