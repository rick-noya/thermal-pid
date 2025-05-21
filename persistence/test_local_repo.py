from dotenv import load_dotenv
load_dotenv()
from .supabase import SupabaseRepository
from datetime import datetime, timezone
import numpy as np

if __name__ == "__main__":
    repo = SupabaseRepository()
    sample_name = "714"  # Change to a sample_name that exists in your Supabase
    sample_id = repo.get_sample_id_by_name(sample_name)
    print("Sample ID:", sample_id)
    assert sample_id, "Sample not found!"

    # Test trend rows
    trend_rows = [
        {"ts": datetime.now(timezone.utc).isoformat(), "max": 100.0, "min": 20.0, "avg": 60.0, "voltage": 2.5, "sample_name": sample_name, "sample_id": sample_id}
    ]
    repo.save_trend_rows(trend_rows)

    # Test heatmaps
    fake_heatmap = np.random.rand(62, 80)
    heatmap_rows = [
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "sample_id": sample_id,
            "camera_id": "TestCamera",
            "heatmap": fake_heatmap.flatten().tolist(),
            "dims": fake_heatmap.shape,
            "aggregation_mode": "raw",
            "metadata": None
        }
    ]
    repo.save_heatmaps(heatmap_rows)

    # Test snapshots (assumes test.png exists in the current directory)
    snapshot_rows = [
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "sample_id": sample_id,
            "camera_id": "TestCamera",
            "file_type": "png",
            "local_path": "test.png"
        }
    ]
    repo.save_snapshots(snapshot_rows) 