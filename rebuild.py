# rebuild_from_cache.py

import json
import os
from concurrent.futures import ThreadPoolExecutor
from re_classify_2 import process_link # We reuse the processing logic from your existing tool

CACHE_FILE = "thumbnail_cache.json"
OUTPUT_FILE = "classified_videos.txt"
BACKUP_FILE = "classified_videos.txt.bak"

def rebuild_from_cache():
    """
    Reads all video links from the JSON cache, re-classifies them,
    and rebuilds the classified_videos.txt file from scratch.
    """
    if not os.path.exists(CACHE_FILE):
        print(f"Error: Cache file '{CACHE_FILE}' not found. Cannot rebuild.")
        return

    print(f"Reading links from '{CACHE_FILE}'...")
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        try:
            thumbnail_cache = json.load(f)
        except json.JSONDecodeError:
            print(f"Error: Could not read '{CACHE_FILE}'. It might be corrupted.")
            return
            
    urls_to_process = list(thumbnail_cache.keys())
    
    if not urls_to_process:
        print("No video links found in the cache file.")
        return

    print(f"Found {len(urls_to_process)} links. Starting rebuild process...")
    print("This may take a while depending on the number of videos.")

    # --- Process all links using the existing logic ---
    updated_lines = []
    # Using ThreadPoolExecutor to speed up the process significantly
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(process_link, urls_to_process)
        for result in results:
            if result and "[Failed to process]" not in result:
                updated_lines.append(result)
                print(f"  -> Re-classified: {result.split(' | ')[0]}")
            elif result:
                 print(f"  -> Failed to process a link.")


    # --- Backup the old file just in case ---
    if os.path.exists(OUTPUT_FILE):
        print(f"Backing up existing '{OUTPUT_FILE}' to '{BACKUP_FILE}'...")
        os.rename(OUTPUT_FILE, BACKUP_FILE)

    # --- Write the new, complete file ---
    print(f"Writing {len(updated_lines)} videos to '{OUTPUT_FILE}'...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(updated_lines) + "\n")

    print("\n✅ Rebuild complete!")
    print(f"'{OUTPUT_FILE}' has been successfully rebuilt from the cache.")

if __name__ == "__main__":
    rebuild_from_cache()