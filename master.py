import requests
from bs4 import BeautifulSoup
import time
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://www.google.com"
}

def get_video_title(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            print(f"Failed to access {url} (status {response.status_code})")
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.text.strip().replace(" - Pornhub.com", "").strip()
        return None
    except Exception as e:
        print(f"Error fetching title for {url}: {e}")
        return None

def get_video_tags(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        tag_elements = soup.find_all("a", href=re.compile(r"/video/search\?search="))
        tags = [tag.text.strip().lower() for tag in tag_elements]
        return tags

    except Exception as e:
        print(f"Error fetching tags for {url}: {e}")
        return []

def classify(tags):
    if "lesbian" in tags:
        return "lesbian"
    if any("f/f/f" in tag or "fff" in tag for tag in tags):
        return "threesome (f/f/f)"
    if any(tag in ["threesome", "mff", "m/f/f"] for tag in tags):
        return "threesome (m/f/f)"
    if "straight" in tags or ("female" in tags and "male" in tags):
        return "straight"
    return "unknown"

def process_link(url, links_fp, titled_fp, classified_fp):
    url = url.strip()
    if not url:
        return

    print(f"\nProcessing: {url}")
    
    # Append raw link
    links_fp.write(url + "\n")

    # Get title
    title = get_video_title(url)
    if not title:
        title = "[Title not found]"
    titled_fp.write(f"{title} - {url}\n")

    # Get tags and classify
    tags = get_video_tags(url)
    label = classify(tags)
    classified_fp.write(f"{title} ({label}) - {url}\n")

    time.sleep(1.5)

def main():
    user_input = input("Enter a Pornhub link or a comma-separated list of links:\n> ")

    links = [link.strip() for link in user_input.split(",") if link.strip()]

    with open("links.txt", "a", encoding="utf-8") as links_fp, \
         open("titled_links.txt", "a", encoding="utf-8") as titled_fp, \
         open("classified_videos.txt", "a", encoding="utf-8") as classified_fp:

        for url in links:
            process_link(url, links_fp, titled_fp, classified_fp)

    print("\n✅ All done. Links processed and added to all files.")

if __name__ == "__main__":
    main()
