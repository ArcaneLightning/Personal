import requests
from bs4 import BeautifulSoup
import time
import re
import os
from concurrent.futures import ThreadPoolExecutor

# --- Configuration ---
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Referer": "https://www.google.com"
}
OUTPUT_FILE = "classified_videos.txt"

# --- Core Functions ---

def fetch_video_details(url):
    """
    Fetches title, actors (with genders), and tags in a single request.
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        title_tag = soup.find("title")
        title = "Untitled"
        if title_tag:
            title = title_tag.text.strip().replace(" - Pornhub.com", "").strip()

        male_actors, female_actors, trans_actors = set(), set(), set()
        actor_wrapper = soup.select_one('.pstar-list-btn')
        if actor_wrapper:
            actor_links = actor_wrapper.find_all('a', href=re.compile(r'/pornstar/'))
            for link in actor_links:
                actor_name = link.text.strip()
                if link.find("i", class_="icon-male"): male_actors.add(actor_name)
                elif link.find("i", class_="icon-female"): female_actors.add(actor_name)
                elif link.find("i", class_="icon-trans"): trans_actors.add(actor_name)
        
        tag_elements = soup.find_all("a", href=re.compile(r"/video/search\?search=|/tag/"))
        tags = {tag.text.strip().lower() for tag in tag_elements if tag.text.strip()}

        return title, tags, list(male_actors), list(female_actors), list(trans_actors)

    except requests.exceptions.RequestException as e:
        print(f"Error fetching details for {url}: {e}")
        return "Untitled", set(), [], [], []

def classify_by_tags(tags):
    """Fallback classification based on tags if actor info is unavailable."""
    tags_lower = {tag.lower() for tag in tags}
    if "orgy" in tags_lower: return "Orgy"
    if "foursome" in tags_lower: return "Foursome"
    LESBIAN_KEYWORDS = {"lesbian", "girl on girl", "f/f", "dyke", "tribbing", "pussy licking", "scissoring"}
    if any(k in tags_lower for k in LESBIAN_KEYWORDS): return "Lesbian"
    if "straight" in tags_lower: return "Straight"
    if len(tags_lower) > 2: return "Straight"
    return "Unknown"

def classify(tags, male_actors, female_actors, trans_actors):
    """
    REVISED: Main classification logic that prioritizes actors and includes Foursome/Orgy.
    """
    male_count, female_count, trans_count = len(male_actors), len(female_actors), len(trans_actors)
    total_actors = male_count + female_count + trans_count

    if total_actors > 0:
        if trans_count > 0: return "Trans"

        # Check for larger groups first
        if total_actors >= 5: return "Orgy"
        if total_actors == 4: return "Foursome"

        if total_actors == 3:
            if female_count == 3 and male_count == 0: return "Threesome (FFF)"
            if male_count == 2 and female_count == 1: return "Threesome (MMF)"
            if female_count == 2 and male_count == 1: return "Threesome (FFM)"
            if male_count == 3 and female_count == 0: return "Threesome (MMM)"
            if "mmf" in tags or "m/m/f" in tags: return "Threesome (MMF)"
            if "ffm" in tags or "f/f/m" in tags or "mff" in tags: return "Threesome (FFM)"
            return "Threesome"

        if total_actors == 2:
            if female_count == 2: return "Lesbian"
            if male_count == 2: return "Gay"
            if male_count == 1 and female_count == 1: return "Straight"
        
        if total_actors == 1:
            if female_count == 1: return "Solo (Female)"
            if male_count == 1: return "Solo (Male)"
    
    return classify_by_tags(tags)

def process_link(url):
    url = url.strip()
    if not url: return None
    print(f"Processing: {url}")
    title, tags, male_actors, female_actors, trans_actors = fetch_video_details(url)
    if title == "Untitled" and not tags and not male_actors and not female_actors:
        return f"[Failed to process] - {url}"
    label = classify(tags, male_actors, female_actors, trans_actors)
    time.sleep(1) 
    return f"{title} ({label}) - {url}"

def process_new_links():
    user_input = input("\nEnter a Pornhub link or a comma-separated list of links:\n> ")
    links = [link.strip() for link in user_input.split(",") if link.strip()]
    if not links:
        print("No valid links provided.")
        return
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        for url in links:
            result_line = process_link(url)
            if result_line:
                print(f"  -> Classified as: {result_line.split('(')[1].split(')')[0]}")
                f.write(result_line + "\n")
    print("\n✅ All new links processed and added to the file.")

def reclassify_existing_videos():
    if not os.path.exists(OUTPUT_FILE):
        print(f"Error: '{OUTPUT_FILE}' not found. There is nothing to re-classify.")
        return
    print("Reading existing videos...")
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    urls_to_reclassify = [re.search(r"https?://[^\s)]+", line).group(0) for line in lines if re.search(r"https?://[^\s)]+", line)]
    if not urls_to_reclassify:
        print("No URLs found in the file.")
        return
    print(f"Found {len(urls_to_reclassify)} videos. Starting re-classification (this may take a while)...")
    updated_lines = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = executor.map(process_link, urls_to_reclassify)
        for result in results:
            if result:
                updated_lines.append(result)
                print(f"  -> Re-classified: {result}")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(updated_lines) + "\n")
    print(f"\n✅ Re-classification complete. '{OUTPUT_FILE}' has been updated.")

def main():
    while True:
        print("\n--- Video Classification Tool ---")
        print("1. Add and classify new video links")
        print("2. Re-classify all existing videos in the file")
        print("3. Exit")
        choice = input("> ")
        if choice == "1": process_new_links()
        elif choice == "2": reclassify_existing_videos()
        elif choice == "3": break
        else: print("Invalid choice. Please enter 1, 2, or 3.")

if __name__ == "__main__":
    main()
