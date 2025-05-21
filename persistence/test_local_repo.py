from .local import LocalRepository
from datetime import datetime

if __name__ == "__main__":
    repo = LocalRepository()
    # Test trend rows
    trend_rows = [
        {"ts": datetime.now(), "max": 100.0, "min": 20.0, "avg": 60.0, "voltage": 2.5, "sample_name": "TestSample"}
    ]
    repo.save_trend_rows(trend_rows)

    # Test snapshots
    snapshots = [
        {"ts": datetime.now(), "camera_name": "Camera1", "local_path": "/tmp/test.png", "sample_name": "TestSample"}
    ]
    repo.save_snapshots(snapshots) 