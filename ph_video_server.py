from flask import Flask, jsonify, request
from flask_cors import CORS
import re
import requests
from bs4 import BeautifulSoup
import logging
from concurrent.futures import ThreadPoolExecutor
import json
import os
import threading

app = Flask(__name__)
CORS(app)

# --- Configuration ---
VIDEO_FILE = "classified_videos.txt"
CACHE_FILE = "thumbnail_cache.json"
THUMBNAIL_CACHE = {}
cache_lock = threading.Lock()

logging.basicConfig(level=logging.INFO)

# --- Unified Classification Logic ---

def fetch_video_details(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": "https://www.google.com"
        }
        response = requests.get(url, headers=headers, timeout=15)
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
        logging.warning(f"Failed to fetch details from {url}: {e}")
        return "Untitled", set(), [], [], []

def classify_by_tags(tags):
    tags_lower = {tag.lower() for tag in tags}
    if "orgy" in tags_lower: return "Orgy"
    if "foursome" in tags_lower: return "Foursome"
    LESBIAN_KEYWORDS = {"lesbian", "girl on girl", "f/f", "dyke", "tribbing", "pussy licking", "scissoring"}
    if any(k in tags_lower for k in LESBIAN_KEYWORDS): return "Lesbian"
    if "straight" in tags_lower: return "Straight"
    if len(tags_lower) > 2: return "Straight"
    return "Unknown"

def classify(tags, male_actors, female_actors, trans_actors):
    male_count, female_count, trans_count = len(male_actors), len(female_actors), len(trans_actors)
    total_actors = male_count + female_count + trans_count

    if total_actors > 0:
        if trans_count > 0: return "Trans"
        
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

# --- Caching and Thumbnail Logic ---

def load_cache():
    global THUMBNAIL_CACHE
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            try: THUMBNAIL_CACHE = json.load(f)
            except json.JSONDecodeError: THUMBNAIL_CACHE = {}
    logging.info(f"Loaded {len(THUMBNAIL_CACHE)} items from cache.")

def save_cache():
    with cache_lock:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(THUMBNAIL_CACHE, f, indent=4)

def get_or_generate_thumbnail(link):
    if link in THUMBNAIL_CACHE: return THUMBNAIL_CACHE[link]
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(link, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        thumb_tag = soup.find("meta", property="og:image")
        if thumb_tag and thumb_tag.get("content"):
            thumb_url = thumb_tag.get("content")
            THUMBNAIL_CACHE[link] = thumb_url
            save_cache()
            return thumb_url
    except requests.exceptions.RequestException as e:
        logging.warning(f"Thumbnail fetch failed for {link}: {e}")
    no_thumb_url = "https://via.placeholder.com/320x180?text=No+Thumbnail"
    THUMBNAIL_CACHE[link] = no_thumb_url
    save_cache()
    return no_thumb_url

def parse_videos():
    videos = []
    if not os.path.exists(VIDEO_FILE): return []
    with open(VIDEO_FILE, "r", encoding="utf-8") as f:
        for line in f:
            match = re.match(r"^(.*) \((.*?)\) - (https?://.*?)$", line.strip())
            if match:
                title, tag, link = match.groups()
                videos.append({
                    "title": title, "tag": tag, "link": link,
                    "thumb": THUMBNAIL_CACHE.get(link, "https://via.placeholder.com/320x180?text=Loading...")
                })
    return videos

# --- API Endpoints ---

@app.route("/videos")
def get_videos():
    videos = parse_videos()
    links_to_fetch = [v['link'] for v in videos if v['link'] not in THUMBNAIL_CACHE]
    if links_to_fetch:
        with ThreadPoolExecutor(max_workers=10) as executor:
            executor.map(get_or_generate_thumbnail, links_to_fetch)
    for video in videos:
        video['thumb'] = THUMBNAIL_CACHE.get(video['link'])
    return jsonify(videos)

@app.route("/add", methods=["POST"])
def add_video():
    data = request.json
    if not data or not data.get("link"):
        return jsonify({"error": "Missing link"}), 400
    link = data.get("link")
    
    title, tags, male_actors, female_actors, trans_actors = fetch_video_details(link)
    tag = classify(tags, male_actors, female_actors, trans_actors)

    entry = f"{title} ({tag}) - {link}\n"
    try:
        with open(VIDEO_FILE, "a", encoding="utf-8") as f:
            f.write(entry)
        get_or_generate_thumbnail(link)
        return jsonify({"message": "Video added.", "title": title, "tag": tag}), 201
    except Exception as e:
        logging.error(f"Failed to write to file: {e}")
        return jsonify({"error": "Could not save video."}), 500

@app.route("/remove", methods=["DELETE"])
def remove_video():
    data = request.json
    link_to_remove = data.get("link")
    if not link_to_remove:
        return jsonify({"error": "Missing link"}), 400
    if not os.path.exists(VIDEO_FILE):
        return jsonify({"error": "Video file not found."}), 404
    lines_to_keep = []
    removed = False
    with open(VIDEO_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if link_to_remove not in line:
                lines_to_keep.append(line)
            else:
                removed = True
    if not removed:
        return jsonify({"error": "Video not found in file."}), 404
    with open(VIDEO_FILE, "w", encoding="utf-8") as f:
        f.writelines(lines_to_keep)
    if link_to_remove in THUMBNAIL_CACHE:
        del THUMBNAIL_CACHE[link_to_remove]
        save_cache()
    return jsonify({"message": "Video removed successfully."}), 200

if __name__ == "__main__":
    load_cache()
    app.run(debug=True, port=5000)
