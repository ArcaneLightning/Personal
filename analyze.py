import json
import sys

def analyze_counts(posts_data):
    """
    Counts the number of unique posts and images per subreddit.

    - A "post" is a unique combination of an author and title.
    - An "image" is any item with a type of "image".

    Args:
        posts_data (list): A list of post dictionaries from the JSON file.

    Returns:
        dict: A dictionary with subreddit names as keys and their counts as values.
    """
    subreddit_stats = {}

    for item in posts_data:
        raw_subreddit = item.get('subreddit')
        if not raw_subreddit:
            continue # Skip items that don't have a subreddit

        # --- THIS IS THE UPDATED LINE ---
        # Normalize the subreddit name to remove any "r/" prefix
        subreddit = raw_subreddit.split('/')[-1]

        # Initialize the subreddit's stats if it's the first time seeing it
        if subreddit not in subreddit_stats:
            subreddit_stats[subreddit] = {
                "unique_posts": set(),
                "image_count": 0
            }

        # Count the image if the type matches
        if item.get('type') == 'image':
            subreddit_stats[subreddit]["image_count"] += 1

        # Add the unique (author, title) tuple to the set for post counting
        author = item.get('author')
        title = item.get('title')
        if author and title:
            subreddit_stats[subreddit]["unique_posts"].add((author, title))

    return subreddit_stats

# --- Main Script ---
if __name__ == "__main__":
    input_filename = 'cleaned_data.json'

    try:
        with open(input_filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: The file '{input_filename}' was not found.")
        print("Please run the previous script first to generate this file.")
        sys.exit()
    except json.JSONDecodeError:
        print(f"❌ Error: Could not decode JSON from '{input_filename}'.")
        sys.exit()

    print(f"📊 Analyzing '{input_filename}'...\n")

    # Get the stats from the analysis function
    stats = analyze_counts(data)

    if not stats:
        print("No subreddit data could be analyzed.")
    else:
        # Sort the subreddits alphabetically for a clean report
        sorted_subreddits = sorted(stats.keys(), key=lambda s: s.lower())

        print("--- Subreddit Report ---")
        for subreddit in sorted_subreddits:
            post_count = len(stats[subreddit]['unique_posts'])
            image_count = stats[subreddit]['image_count']
            print(f"r/{subreddit:<20} | Posts: {post_count:<5} | Images: {image_count:<5}")
        print("------------------------")