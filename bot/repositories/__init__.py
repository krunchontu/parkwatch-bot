"""Repository modules for ParkWatch SG database layer.

Phase 11.8: Split the monolithic database.py into focused repository classes.
Each repository groups related database operations while sharing the same
underlying connection via BaseRepository.
"""

from .admin import AdminRepository
from .base import BaseRepository
from .config import ConfigRepository
from .feedback import FeedbackRepository
from .sighting import SightingRepository
from .user import UserRepository

__all__ = [
    "AdminRepository",
    "BaseRepository",
    "ConfigRepository",
    "FeedbackRepository",
    "SightingRepository",
    "UserRepository",
]
