# reclassifier.py

import requests
from bs4 import BeautifulSoup
import time
import re
import os
from concurrent.futures import ThreadPoolExecutor
from classification_logic import classify_video

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
}
OUTPUT_FILE = "classified_videos.txt"

def fetch_video_details(url):
    """
    UPDATED: Now scrapes channel name in addition to other details.
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # --- Scrape Title ---
        title_tag = soup.find("title")
        title = "Untitled"
        if title_tag:
            title = title_tag.text.strip().replace(" - Pornhub.com", "").strip()

        # --- Scrape Channel Name ---
        channel_name = "Unknown Channel"
        channel_link = soup.select_one('a[data-mx-cat="Uploader"]')
        if channel_link:
            channel_name = channel_link.text.strip()

        # --- Scrape Actors ---
        male_actors, female_actors, trans_actors = set(), set(), set()
        actor_wrapper = soup.select_one("div.pornstarsWrapper") 
        if actor_wrapper:
            actor_links = actor_wrapper.find_all('a', href=re.compile(r'/pornstar/'))
            for link in actor_links:
                actor_name = link.text.strip()
                if not actor_name: continue
                
                aria_label = link.get('aria-label', '').lower()
                if 'female pornstar' in aria_label:
                    female_actors.add(actor_name)
                elif 'male pornstar' in aria_label:
                    male_actors.add(actor_name)
                elif 'transgender pornstar' in aria_label:
                    trans_actors.add(actor_name)

        # --- Scrape Tags ---
        tag_elements = soup.find_all("a", href=re.compile(r"/video/search\?search=|/tag/"))
        scraped_tags = {tag.text.strip().lower() for tag in tag_elements if tag.text.strip()}

        return title, channel_name, scraped_tags, list(male_actors), list(female_actors), list(trans_actors)

    except requests.exceptions.RequestException as e:
        print(f"Error fetching details for {url}: {e}")
        return "Untitled", "Unknown Channel", set(), [], [], []


def process_link(url):
    url = url.strip()
    if not url: return None
    
    print(f"Processing: {url}")
    title, channel, scraped_tags, males, females, trans = fetch_video_details(url)
    
    if title == "Untitled":
        return f"[Failed to process] | | {url}"
    
    final_tags = classify_video(title, channel, scraped_tags, males, females, trans)
    
    time.sleep(1)
    return f"{title} | {','.join(final_tags)} | {url}"

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
                tags_str = result_line.split(' | ')[1]
                print(f"  -> Classified as: {tags_str}")
                f.write(result_line + "\n")
                
    print("\n✅ All new links processed and added to the file.")

def reclassify_existing_videos():
    if not os.path.exists(OUTPUT_FILE):
        print(f"Error: '{OUTPUT_FILE}' not found. There is nothing to re-classify.")
        return
        
    print("Reading existing videos...")
    urls_to_reclassify = []
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            match = re.search(r'(https?://[^\s]+)', line)
            if match:
                urls_to_reclassify.append(match.group(0))

    if not urls_to_reclassify:
        print("No URLs found in the file.")
        return
        
    print(f"Found {len(urls_to_reclassify)} videos. Starting re-classification...")
    
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