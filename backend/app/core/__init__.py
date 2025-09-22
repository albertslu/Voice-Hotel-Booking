"""
Core package for configuration, database, and shared utilities.
"""

from .config import settings
from .database import db

__all__ = ['settings', 'db']
