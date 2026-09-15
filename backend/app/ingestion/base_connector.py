"""
Provider abstraction layer.

Why this exists:
The project brief calls for swappable data providers. Every connector
(real or mock) implements the same interface, so the rest of the
pipeline (validation, normalization, storage) never needs to know or
care which provider produced the raw data. Adding a new real provider
later means writing one new class here — nothing else changes.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseConnector(ABC):
    """
    Every connector must be able to say which provider it is and
    return games in a common raw shape. Connectors do NOT validate,
    normalize, or store data — that happens in later pipeline stages.
    """

    provider_name: str = "base"

    @abstractmethod
    def fetch_games(self, league_slug: str, date_range: tuple[str, str]) -> List[Dict[str, Any]]:
        """
        Return a list of raw game dicts for the given league and
        date range (ISO date strings, inclusive). The raw shape is
        provider-specific and gets normalized in a later stage.
        """
        raise NotImplementedError
