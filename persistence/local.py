from .base import DataRepository

class LocalRepository(DataRepository):
    def save_trend_rows(self, rows):
        print("Would save trend rows locally:", rows)

    def save_snapshots(self, rows):
        print("Would save snapshots locally:", rows) 