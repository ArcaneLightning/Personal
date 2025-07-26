import logging
import json
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup
from flask import Blueprint, jsonify, request

from classification_logic import classify_video

# Create a Blueprint object
video_bp = Blueprint('video', __name__)

# --- CONFIGURATION AND STATE ---
VIDEO_FILE = "classified_videos.txt"
CACHE_FILE = "thumbnail_cache.json"
THUMBNAIL_CACHE = {}
cache_lock = threading.Lock()

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

logging.basicConfig(level=logging.INFO)


# --- HELPER FUNCTIONS ---
def fetch_video_details(url):
    """Fetches metadata for a given video URL."""
    try:
        response = requests.get(url, timeout=15, headers=REQUEST_HEADERS)
        response.raise_for_status()
        final_url = response.url
        soup = BeautifulSoup(response.text, "html.parser")

        title_tag = soup.find("title")
        title = "Untitled"
        if title_tag:
            title = title_tag.text.strip().replace(" - Pornhub.com", "").strip()

        channel_name = "Unknown Channel"
        channel_link = soup.select_one('a[data-mx-cat="Uploader"]')
        if channel_link:
            channel_name = channel_link.text.strip()

        # Actor and tag scraping logic...
        male_actors, female_actors, trans_actors = set(), set(), set()
        actor_wrapper = soup.select_one("div.pornstarsWrapper")
        if actor_wrapper:
            actor_links = actor_wrapper.find_all('a', href=re.compile(r'/pornstar/'))
            for link in actor_links:
                actor_name = link.text.strip()
                if not actor_name: continue
                aria_label = link.get('aria-label', '').lower()
                if 'female pornstar' in aria_label: female_actors.add(actor_name)
                elif 'male pornstar' in aria_label: male_actors.add(actor_name)
                elif 'transgender pornstar' in aria_label: trans_actors.add(actor_name)

        tag_elements = soup.find_all("a", href=re.compile(r"/video/search\?search=|/tag/"))
        scraped_tags = {tag.text.strip().lower() for tag in tag_elements if tag.text.strip()}
        return title, channel_name, scraped_tags, list(male_actors), list(female_actors), list(trans_actors), final_url
    except requests.exceptions.RequestException as e:
        logging.warning(f"Failed to fetch details from {url}: {e}")
        return "Untitled", "Unknown Channel", set(), [], [], [], url


def get_or_generate_thumbnail(link):
    """Gets a thumbnail from the cache or generates it. This function is thread-safe."""
    with cache_lock:
        if link in THUMBNAIL_CACHE:
            return

    # This part runs if the thumbnail is not in the cache
    thumb_url = "https://via.placeholder.com/320x180?text=Error"
    try:
        response = requests.get(link, timeout=10, headers=REQUEST_HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        thumb_tag = soup.find("meta", property="og:image")
        if thumb_tag and thumb_tag.get("content"):
            thumb_url = thumb_tag.get("content")
    except requests.exceptions.RequestException as e:
        logging.warning(f"Thumbnail fetch failed for {link}: {e}")

    with cache_lock:
        THUMBNAIL_CACHE[link] = thumb_url
    return


def load_cache():
    """Loads the thumbnail cache from a file at startup."""
    global THUMBNAIL_CACHE
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            try:
                THUMBNAIL_CACHE = json.load(f)
            except json.JSONDecodeError:
                THUMBNAIL_CACHE = {}
    logging.info(f"Loaded {len(THUMBNAIL_CACHE)} thumbnail items from cache.")


def save_cache():
    """Saves the current thumbnail cache to a file."""
    with cache_lock:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(THUMBNAIL_CACHE, f, indent=4)


def parse_videos():
    """Parses the video data file."""
    videos = []
    if not os.path.exists(VIDEO_FILE):
        return []
    try:
        with open(VIDEO_FILE, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().rsplit(' | ', 2)
                if len(parts) == 3:
                    title, tags_str, link = parts
                    videos.append({"title": title, "tags": [tag.strip() for tag in tags_str.split(',')], "link": link})
                elif line.strip():
                    logging.warning(f"Skipping malformed line: {line.strip()}")
    except Exception as e:
        logging.error(f"Could not read video file '{VIDEO_FILE}': {e}")
        return []
    return videos


# --- FLASK ROUTES ---
@video_bp.route("/videos")
def get_videos():
    """
    FIXED: Reintroduces parallel fetching for missing thumbnails to prevent server timeouts,
    while enriching the video data correctly from the cache.
    """
    try:
        videos = parse_videos()
        links = [v['link'] for v in videos]

        # Use the ThreadPoolExecutor to fetch any missing thumbnails in parallel.
        # This is fast and prevents timeouts.
        with ThreadPoolExecutor(max_workers=10) as executor:
            executor.map(get_or_generate_thumbnail, links)

        # Now that the cache is populated, enrich the video objects.
        for video in videos:
            video['thumb'] = THUMBNAIL_CACHE.get(video['link'], "https://via.placeholder.com/320x180?text=Error")

        save_cache()  # Save any newly fetched thumbnails to the file.

        return jsonify(videos)
    except Exception as e:
        logging.error(f"An error occurred in /videos endpoint: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred."}), 500


@video_bp.route("/add", methods=["POST"])
def add_video():
    """Adds new videos to the list."""
    # This function remains correct.
    data = request.json
    urls = data.get("urls")
    if not urls or not isinstance(urls, list):
        return jsonify({"error": "A list of URLs is required."}), 400

    results = []
    existing_links = {v['link'] for v in parse_videos()}
    any_success = False

    with open(VIDEO_FILE, "a", encoding="utf-8") as f:
        for url in urls:
            try:
                title, channel, scraped_tags, males, females, trans, final_url = fetch_video_details(url)
                if title == "Untitled":
                    raise Exception("Failed to fetch video details")
                if final_url in existing_links:
                    results.append({"status": "duplicate", "url": final_url})
                    continue

                final_tags = classify_video(title, channel, scraped_tags, males, females, trans)
                entry = f"{title} | {','.join(final_tags)} | {final_url}\n"
                f.write(entry)
                get_or_generate_thumbnail(final_url)

                results.append({"status": "success", "title": title, "final_url": final_url})
                existing_links.add(final_url)
                any_success = True
            except Exception as e:
                logging.error(f"Error processing url {url}: {e}")
                results.append({"status": "error", "url": url, "reason": str(e)})

    if any_success:
        save_cache()

    return jsonify(results), 201


@video_bp.route("/remove", methods=["DELETE"])
def remove_video():
    """Removes a video from the list."""
    # This function remains correct.
    data = request.json
    link_to_remove = data.get("link")
    if not link_to_remove:
        return jsonify({"error": "Missing link"}), 400
    if not os.path.exists(VIDEO_FILE):
        return jsonify({"error": "Video file not found."}), 404

    lines_to_keep, removed = [], False
    with open(VIDEO_FILE, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().rsplit(' | ', 2)
            if len(parts) == 3 and parts[2] == link_to_remove:
                removed = True
            else:
                lines_to_keep.append(line)

    if not removed:
        return jsonify({"error": "Video not found in file."}), 404

    with open(VIDEO_FILE, "w", encoding="utf-8") as f:
        f.writelines(lines_to_keep)

    with cache_lock:
        if link_to_remove in THUMBNAIL_CACHE:
            del THUMBNAIL_CACHE[link_to_remove]
            save_cache()

    return jsonify({"message": "Video removed successfully."}), 200