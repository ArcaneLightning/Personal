import json
import sys
import shutil
from datetime import datetime

def find_duplicates(posts_data):
    """
    Identifies posts with the same title, media_url, and subreddit.
    """
    seen = set()
    duplicates = []
    for post in posts_data:
        # Create a unique identifier based on title, media_url, and subreddit
        identifier = (post.get('title'), post.get('media_url'), post.get('subreddit'))
        if identifier in seen:
            duplicates.append(post)
        else:
            seen.add(identifier)
    return duplicates

def remove_duplicates(posts_data):
    """
    Removes duplicate posts, keeping the first occurrence.
    """
    seen = set()
    unique_posts = []
    for post in posts_data:
        identifier = (post.get('title'), post.get('media_url'), post.get('subreddit'))
        if identifier not in seen:
            seen.add(identifier)
            unique_posts.append(post)
    return unique_posts

# --- Main Script ---
if __name__ == "__main__":
    input_filename = 'reddit_gallery.json'
    data = []

    # --- Load data from the specified JSON file ---
    try:
        with open(input_filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"✅ Successfully loaded {len(data)} posts from '{input_filename}'.")
    except FileNotFoundError:
        print(f"❌ Error: The file '{input_filename}' was not found.")
        print("Please make sure it's in the same directory as this script.")
        sys.exit()
    except json.JSONDecodeError:
        print(f"❌ Error: Could not decode JSON from '{input_filename}'. The file may be corrupt or empty.")
        sys.exit()
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit()

    print("\n🔍 Searching for duplicate posts based on title, URL, and subreddit...")
    duplicate_items = find_duplicates(data)

    if not duplicate_items:
        print("\n✅ No duplicate posts found.")
    else:
        print(f"\n🚨 Found {len(duplicate_items)} duplicate post(s):")
        for item in duplicate_items:
            print(f"  - Title: \"{item.get('title')}\", Subreddit: r/{item.get('subreddit')}")

        choice = input("\nDo you want to remove these duplicates and create a clean file? (y/n): ").lower()

        if choice == 'y':
            # --- Create a timestamped backup ---
            try:
                timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
                backup_filename = f"{input_filename}.backup_{timestamp}"
                shutil.copy(input_filename, backup_filename)
                print(f"\n🔒 A backup of your original file has been created: '{backup_filename}'")
            except Exception as e:
                print(f"\n⚠️ Warning: Could not create backup file. Error: {e}")

            # --- Remove duplicates and save the new file ---
            cleaned_data = remove_duplicates(data)
            output_filename = 'cleaned_data.json'
            
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump(cleaned_data, f, indent=4, ensure_ascii=False)
            
            print(f"✨ Duplicates removed. Clean data saved to '{output_filename}'.")
            print(f"Original post count: {len(data)}. New post count: {len(cleaned_data)}.")
        else:
            print("\n👍 No changes made. Exiting.")