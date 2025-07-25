# tag_updater.py

import time
from gallery import scrape_page, load_data, save_data

def update_missing_tags():
    """
    Finds items with empty tag lists in the database and re-scrapes them
    to fill in the missing tags.
    """
    print("Loading gallery data...")
    all_data = load_data()
    
    # Find all items that have a missing or empty 'tags' list
    items_to_update = []
    for index, item in enumerate(all_data):
        if not item.get("tags"): # This checks for missing key or empty list
            items_to_update.append((index, item))

    if not items_to_update:
        print("✅ No items with missing tags found.")
        return

    print(f"Found {len(items_to_update)} items with missing tags.")
    
    try:
        choice = input("Do you want to attempt to re-scrape them now? (y/n): ").lower()
        if choice != 'y':
            print("Operation cancelled.")
            return
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
        return

    successful_updates = 0
    for index, item in items_to_update:
        source_url = item.get("source_url")
        item_id = item.get("id")
        print(f"\nUpdating item ID: {item_id}...")
        
        if not source_url:
            print(f"  - Skipping item {item_id}: No source URL found.")
            continue

        try:
            scraped_item, error = scrape_page(source_url)
            if error:
                print(f"  - Error scraping {source_url}: {error}")
                continue

            if scraped_item and scraped_item.get("tags"):
                # Update the original item in the list with the new tags
                all_data[index]["tags"] = scraped_item["tags"]
                successful_updates += 1
                print(f"  - Success! Found {len(scraped_item['tags'])} tags.")
            else:
                print("  - Scrape succeeded, but no tags were found.")
            
            time.sleep(1) # Be respectful to the server

        except Exception as e:
            print(f"  - A critical error occurred: {e}")

    if successful_updates > 0:
        print(f"\nSuccessfully updated tags for {successful_updates} items.")
        print("Saving updated data to gallery_data.json...")
        save_data(all_data)
        print("✅ Done.")
    else:
        print("\nNo items were updated.")


if __name__ == "__main__":
    update_missing_tags()