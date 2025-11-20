from __future__ import annotations

from datetime import date
from typing import Iterable

from .base import BaseConnector
from src.core.schema import CanonDoc, Chunk, ItemRef, RawDoc


class MevzuatMBSConnector(BaseConnector):
    source = "MBS"

    def list_items(self, since: date) -> Iterable[ItemRef]:
        return []

    def fetch(self, ref: ItemRef) -> RawDoc:
        raise NotImplementedError

    def parse(self, raw: RawDoc) -> CanonDoc:
        raise NotImplementedError

    def chunk(self, doc: CanonDoc) -> list[Chunk]:
        raise NotImplementedError
