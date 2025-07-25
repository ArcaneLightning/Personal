# remove_duplicates_by_id.py

import json
import os
import shutil

# --- Configuration ---
# List of the JSON database files you want to clean.
FILES_TO_CLEAN = [
    "gallery_data.json",
    "reddit_gallery.json"
]

def clean_duplicates_from_file(filename):
    """
    Reads a JSON file, removes duplicate entries based on the 'id' field,
    and saves the cleaned data back to the file.
    """
    print(f"--- Processing: {filename} ---")

    if not os.path.exists(filename):
        print(f"File not found. Skipping.")
        return

    # Load the data from the file
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error reading file: {e}. Skipping.")
        return

    if not isinstance(data, list):
        print("Data is not a list. Skipping.")
        return

    # --- Find and remove duplicates ---
    unique_items = []
    seen_ids = set()
    duplicates_found = 0

    for item in data:
        # Ensure the item is a dictionary and has an 'id'
        if isinstance(item, dict) and "id" in item:
            item_id = item["id"]
            if item_id not in seen_ids:
                unique_items.append(item)
                seen_ids.add(item_id)
            else:
                duplicates_found += 1
        else:
            # Keep items that don't have an ID (e.g., corrupted entries)
            unique_items.append(item)
    
    # --- Save the cleaned data if changes were made ---
    if duplicates_found > 0:
        print(f"Found and removed {duplicates_found} duplicate(s).")
        
        # Create a backup
        backup_filename = f"{filename}.bak"
        print(f"Backing up original file to '{backup_filename}'...")
        shutil.copy(filename, backup_filename)

        # Save the cleaned data
        print(f"Saving cleaned data back to '{filename}'...")
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(unique_items, f, indent=4)
        
        print("✅ File cleaned successfully.")
    else:
        print("✅ No duplicates found.")


if __name__ == "__main__":
    for file in FILES_TO_CLEAN:
        clean_duplicates_from_file(file)
        print("-" * 25)
    print("All files have been processed.")