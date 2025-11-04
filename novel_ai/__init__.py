"""
NovelAI - AI小说写作工具
"""

from .core.project import NovelProject, Chapter, Character
from .core.context_manager import ContextManager
from .api.grok_client import GrokClient

__version__ = "1.0.0"
__all__ = ["NovelProject", "Chapter", "Character", "ContextManager", "GrokClient"]
