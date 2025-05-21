from dotenv import load_dotenv
load_dotenv()
import os
import logging
from datetime import datetime, timezone
from persistence.supabase import SupabaseRepository

logging.basicConfig(level=logging.INFO)

# Check for required Supabase environment variables
if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_ANON_KEY"):
    raise RuntimeError("Supabase environment variables are not set. Please check your .env file or environment.")

TEST_SAMPLE_NAME = "test_sample"
TEST_TIMESTAMP = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
CSV_FILENAME = f"{TEST_SAMPLE_NAME}_trend_{TEST_TIMESTAMP}.csv"

# 1. Create a dummy trend graph CSV file
headers = ["Timestamp (PST)", "Max Temp (C)", "Min Temp (C)", "Avg Temp (C)", "Voltage (V)", "Event"]
data_rows = [
    ["2024-06-01 12:00:00 PST", 100.0, 20.0, 60.0, 2.5, "Start"],
    ["2024-06-01 12:01:00 PST", 105.0, 22.0, 63.0, 2.7, "Step"],
    ["2024-06-01 12:02:00 PST", 110.0, 25.0, 67.0, 2.9, "End"],
]

logging.info(f"Creating dummy trend graph CSV: {CSV_FILENAME}")
with open(CSV_FILENAME, "w", encoding="utf-8") as f:
    f.write(",".join(headers) + "\n")
    for row in data_rows:
        f.write(",".join(str(x) for x in row) + "\n")

# 2. Upload the CSV to Supabase bucket using the repo
repo = SupabaseRepository()
dest_key = CSV_FILENAME
logging.info(f"Uploading {CSV_FILENAME} to Supabase bucket 'joule-heat-charts' as '{dest_key}'...")
repo.upload_trend_csv(CSV_FILENAME, dest_key)

# 3. Clean up the test CSV file
ios_remove_failed = False
try:
    os.remove(CSV_FILENAME)
    logging.info(f"Deleted local test CSV: {CSV_FILENAME}")
except Exception as e:
    logging.warning(f"Failed to delete local test CSV: {e}")
    ios_remove_failed = True

logging.info("Test complete. Check Supabase bucket for uploaded file.")
if ios_remove_failed:
    logging.info(f"Manual cleanup may be required for: {CSV_FILENAME}") 