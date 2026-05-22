import json
import time
import os

def monitor():
    stats_file = 'logs/ingestion_stats.json'
    print("\n" + "="*60)
    print("      FAILURERAG INGESTION MONITOR")
    print("="*60)
    
    last_processed = -1
    
    try:
        while True:
            if os.path.exists(stats_file):
                try:
                    with open(stats_file) as f:
                        stats = json.load(f)
                    
                    success = stats.get("successful_papers", 0)
                    total = stats.get("total_papers", 0)
                    inserted = stats.get("total_points_inserted", {})
                    
                    if success != last_processed:
                        print(f"[{time.strftime('%H:%M:%S')}] Papers: {success}/{total} | "
                              f"Docs: {inserted.get('document', 0)} | "
                              f"Sem: {inserted.get('semantic', 0)} | "
                              f"Props: {inserted.get('proposition', 0)}", flush=True)
                        last_processed = success
                except (json.JSONDecodeError, IOError):
                    pass # File might be locked while writing
            else:
                print(f"[{time.strftime('%H:%M:%S')}] Waiting for stats file...", flush=True)
            
            time.sleep(10)
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")

if __name__ == "__main__":
    monitor()
