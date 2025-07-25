# sort_videos.py

import os
import re

# --- Configuration ---
# The new, unordered file that you want to sort.
MAIN_FILE = "classified_videos.txt"
# The backup file that has the correct, original order.
ORDER_TEMPLATE_FILE = "classified_videos.txt.bak"
# A final backup of the file before we overwrite it.
FINAL_BACKUP_FILE = "classified_videos.txt.pre-sort.bak"

def extract_url(line):
    """Utility function to extract the URL from a line."""
    match = re.search(r'(https?://[^\s]+)', line)
    return match.group(0) if match else None

def sort_file_by_template():
    """
    Sorts the main video file based on the order of URLs in a template file,
    and appends any new videos to the end.
    """
    if not os.path.exists(MAIN_FILE):
        print(f"Error: Main file '{MAIN_FILE}' not found. Nothing to sort.")
        return
        
    if not os.path.exists(ORDER_TEMPLATE_FILE):
        print(f"Error: Order template file '{ORDER_TEMPLATE_FILE}' not found. Cannot determine order.")
        return

    print(f"Reading desired order from '{ORDER_TEMPLATE_FILE}'...")
    with open(ORDER_TEMPLATE_FILE, "r", encoding="utf-8") as f:
        ordered_urls = [extract_url(line) for line in f if extract_url(line)]

    print(f"Reading current data from '{MAIN_FILE}'...")
    with open(MAIN_FILE, "r", encoding="utf-8") as f:
        # Create a lookup map: {url: "full line of text"}
        current_video_map = {extract_url(line): line.strip() for line in f if extract_url(line)}

    # --- Build the new, sorted list ---
    sorted_lines = []
    
    # 1. Add videos that are in the template file, in the correct order.
    print("Sorting existing videos...")
    for url in ordered_urls:
        if url in current_video_map:
            sorted_lines.append(current_video_map[url])
    
    # 2. Find and add the new videos that are not in the template file.
    print("Finding and appending new videos...")
    template_url_set = set(ordered_urls)
    new_videos_added = 0
    for url, line in current_video_map.items():
        if url not in template_url_set:
            sorted_lines.append(line)
            new_videos_added += 1
            
    print(f"Found {new_videos_added} new videos to append.")

    # --- Backup and write the final file ---
    print(f"Backing up '{MAIN_FILE}' to '{FINAL_BACKUP_FILE}' before overwriting...")
    os.rename(MAIN_FILE, FINAL_BACKUP_FILE)
    
    print(f"Writing {len(sorted_lines)} videos to the newly sorted '{MAIN_FILE}'...")
    with open(MAIN_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted_lines) + "\n")
        
    print("\n✅ Sorting complete!")
    print(f"'{MAIN_FILE}' is now sorted according to the backup file, with new videos at the end.")


if __name__ == "__main__":
    sort_file_by_template()