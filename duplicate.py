# deduplicate.py

import os
import re

# --- Configuration ---
VIDEO_FILE = "classified_videos.txt"
BACKUP_FILE = "classified_videos.txt.pre-dedupe3.bak"

def extract_url(line):
    """Utility function to extract the URL from a line."""
    match = re.search(r'(https?://[^\s]+)', line)
    return match.group(0) if match else None

def find_and_remove_duplicates():
    """
    Scans the video file for duplicate URLs, reports them, and prompts the user
    for removal.
    """
    if not os.path.exists(VIDEO_FILE):
        print(f"Error: Video file '{VIDEO_FILE}' not found.")
        return

    print(f"Scanning '{VIDEO_FILE}' for duplicates...")

    # --- Read the file and identify duplicates ---
    lines = []
    with open(VIDEO_FILE, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    # A dictionary to hold all lines grouped by URL
    videos_by_url = {}
    for line in lines:
        url = extract_url(line)
        if not url:
            continue
        if url not in videos_by_url:
            videos_by_url[url] = []
        videos_by_url[url].append(line)

    # Filter down to only the URLs that have duplicates
    duplicate_groups = {url: lines for url, lines in videos_by_url.items() if len(lines) > 1}

    # --- Report duplicates to the user ---
    if not duplicate_groups:
        print("✅ No duplicate videos found.")
        return

    print("\n--- Found Duplicates ---")
    for url, dup_lines in duplicate_groups.items():
        print(f"URL: {url} (Found {len(dup_lines)} times)")
        for line in dup_lines:
            print(f"  - {line}")
        print("-" * 20)

    # --- Prompt for removal ---
    try:
        choice = input("\nDo you want to remove these duplicates, keeping one of each? (y/n): ").lower()
    except KeyboardInterrupt:
        print("\nOperation cancelled. No changes were made.")
        return

    if choice != 'y':
        print("No changes were made.")
        return

    # --- Proceed with removing duplicates ---
    print("Removing duplicates...")

    # Create a final list, keeping only the first entry for each URL
    unique_lines = []
    seen_urls = set()
    for line in lines:
        url = extract_url(line)
        if url not in seen_urls:
            unique_lines.append(line)
            seen_urls.add(url)

    # Backup the original file
    print(f"Backing up current file to '{BACKUP_FILE}'...")
    os.rename(VIDEO_FILE, BACKUP_FILE)

    # Write the cleaned list to the new file
    print(f"Writing {len(unique_lines)} unique videos back to '{VIDEO_FILE}'...")
    with open(VIDEO_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(unique_lines) + "\n")

    print("\n✅ Duplicates removed successfully!")


if __name__ == "__main__":
    find_and_remove_duplicates()