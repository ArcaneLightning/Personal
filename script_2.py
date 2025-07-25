import requests
from bs4 import BeautifulSoup
import time
import re

def get_video_tags(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://www.google.com"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "html.parser")

        # Try to find tags/categories
        tag_elements = soup.find_all("a", href=re.compile(r"/video/search\?search="))
        tags = [tag.text.strip().lower() for tag in tag_elements]
        return tags

    except Exception as e:
        print(f"Error processing {url}: {e}")
        return []

def classify(tags):
    # Check for lesbian
    if "lesbian" in tags:
        return "lesbian"
    
    # Check for 3+ women
    if any("f/f/f" in tag or "fff" in tag for tag in tags):
        return "threesome (f/f/f)"
    
    # Check for m/f/f or similar
    if any(tag in ["threesome", "mff", "m/f/f"] for tag in tags):
        return "threesome (m/f/f)"

    # Default to straight if one man + one woman implied
    if "straight" in tags or ("female" in tags and "male" in tags):
        return "straight"
    
    return "unknown"

def main():
    input_file = "titled_links.txt"
    output_file = "classified_videos.txt"

    with open(input_file, "r", encoding="utf-8") as infile, open(output_file, "w", encoding="utf-8") as outfile:
        for line in infile:
            if " - " not in line:
                continue

            title, url = line.strip().rsplit(" - ", 1)
            print(f"Processing: {title}")

            tags = get_video_tags(url)
            label = classify(tags)
            outfile.write(f"{title} ({label}) - {url}\n")

            time.sleep(1.5)  # be polite

    print(f"\nDone. Output saved to '{output_file}'.")

if __name__ == "__main__":
    main()
