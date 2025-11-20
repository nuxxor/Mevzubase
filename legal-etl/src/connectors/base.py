from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Iterable

from src.core.schema import CanonDoc, Chunk, ItemRef, RawDoc


class BaseConnector(ABC):
    source: str

    @abstractmethod
    def list_items(self, since: date) -> Iterable[ItemRef]:
        """Return references updated/created since date."""

    @abstractmethod
    def fetch(self, ref: ItemRef) -> RawDoc:
        """Retrieve the raw payload for a reference."""

    @abstractmethod
    def parse(self, raw: RawDoc) -> CanonDoc:
        """Parse raw payload into canonical document."""

    @abstractmethod
    def chunk(self, doc: CanonDoc) -> list[Chunk]:
        """Produce chunks for embedding/indexing."""
