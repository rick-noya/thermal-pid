from .base import DataRepository
from config import get_supabase_config
import os

try:
    from supabase import create_client
except ImportError:
    create_client = None

class SupabaseRepository(DataRepository):
    def __init__(self):
        cfg = get_supabase_config()
        if create_client is None:
            raise ImportError("supabase-py is not installed.")
        self.client = create_client(cfg["url"], cfg["key"])
        self.bucket = cfg["bucket"]

    def save_trend_rows(self, rows):
        try:
            response = self.client.table("joule_heat_trend").insert(rows).execute()
            print("Inserted trend rows to Supabase:", response)
        except Exception as e:
            print(f"Error inserting trend rows to Supabase: {e}")

    def save_snapshots(self, rows):
        meta = []
        for r in rows:
            local_path = r.get("local_path")
            if not local_path or not os.path.exists(local_path):
                print(f"File not found: {local_path}")
                continue
            key = f"{r.get('sample_id','unknown')}/{r.get('camera_id','unknown')}/{os.path.basename(local_path)}"
            try:
                with open(local_path, "rb") as f:
                    upload_resp = self.client.storage.from_(self.bucket).upload(key, f)
                print(f"Uploaded {local_path} to bucket as {key}: {upload_resp}")
                # Remove local_path from metadata row
                meta_row = {k: v for k, v in r.items() if k != "local_path"}
                meta_row["storage_path"] = key
                meta.append(meta_row)
            except Exception as e:
                print(f"Error uploading {local_path} to Supabase Storage: {e}")
        if meta:
            try:
                response = self.client.table("snapshots").insert(meta).execute()
                print("Inserted snapshot metadata to Supabase:", response)
            except Exception as e:
                print(f"Error inserting snapshot metadata to Supabase: {e}")

    def get_sample_id_by_name(self, sample_name):
        """Return the sample_id for a given sample_name, or None if not found."""
        try:
            resp = self.client.table("samples").select("id").eq("sample_name", sample_name).single().execute()
            if resp.data and 'id' in resp.data:
                return resp.data['id']
            else:
                print(f"Sample name '{sample_name}' not found in samples table.")
                return None
        except Exception as e:
            print(f"Error querying sample_id for '{sample_name}': {e}")
            return None

    def save_heatmaps(self, rows):
        try:
            # Convert dims tuple to list for each row
            payload = [dict(r, dims=list(r["dims"])) for r in rows]
            response = self.client.table("camera_heatmaps").insert(payload).execute()
            print("Inserted heatmap rows to Supabase:", response)
        except Exception as e:
            print(f"Error inserting heatmap rows to Supabase: {e}")

    def upload_trend_csv(self, local_path, dest_key):
        """Upload a trend CSV file to the 'joule-heat-charts' bucket in Supabase Storage."""
        if not local_path or not os.path.exists(local_path):
            print(f"Trend CSV file not found: {local_path}")
            return
        bucket_name = "joule-heat-charts"
        try:
            with open(local_path, "rb") as f:
                upload_resp = self.client.storage.from_(bucket_name).upload(dest_key, f, {
                    "content-type": "text/csv"
                })
            print(f"Uploaded trend CSV {local_path} to bucket '{bucket_name}' as '{dest_key}': {upload_resp}")
        except Exception as e:
            print(f"Error uploading trend CSV {local_path} to Supabase Storage: {e}") 