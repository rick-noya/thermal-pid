from abc import ABC, abstractmethod
from typing import Iterable, Dict, Any

class DataRepository(ABC):
    @abstractmethod
    def save_trend_rows(self, rows: Iterable[Dict[str, Any]]) -> None:
        pass

    @abstractmethod
    def save_snapshots(self, rows: Iterable[Dict[str, Any]]) -> None:
        pass 