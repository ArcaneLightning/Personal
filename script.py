import requests
from bs4 import BeautifulSoup
import time

def get_video_title(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://www.google.com"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"Failed to access {url} (status {response.status_code})")
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        # Pornhub titles are usually in <title> but have " - Pornhub.com" appended
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.text.strip().replace(" - Pornhub.com", "").strip()
            return title
        return None
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def main():
    input_file = "links.txt"
    output_file = "titled_links.txt"

    with open(input_file, "r") as infile, open(output_file, "w", encoding="utf-8") as outfile:
        for line in infile:
            url = line.strip()
            if not url:
                continue
            print(f"Processing: {url}")
            title = get_video_title(url)
            if title:
                outfile.write(f"{title} - {url}\n")
            else:
                outfile.write(f"[Title not found] - {url}\n")
            time.sleep(1.5)  # polite delay to avoid getting IP blocked

    print(f"\nDone. Titles saved to '{output_file}'.")

if __name__ == "__main__":
    main()
