from flask import Blueprint, jsonify, request
import re
import requests
from bs4 import BeautifulSoup
import logging
from concurrent.futures import ThreadPoolExecutor
import json
import os
import threading
from classification_logic import classify_video # Assuming this file exists and is correct

# Create a Blueprint object
video_bp = Blueprint('video', __name__)

# --- CONFIGURATION AND STATE ---
VIDEO_FILE = "classified_videos.txt"
CACHE_FILE = "thumbnail_cache.json"
THUMBNAIL_CACHE = {}
cache_lock = threading.Lock()

http_session = requests.Session()
http_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
})

logging.basicConfig(level=logging.INFO)

# --- HELPER FUNCTIONS ---

def fetch_video_details(url):
    try:
        response = http_session.get(url, timeout=15)
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
    """
    FIXED: Fetches a thumbnail if it's a cache miss but no longer saves the
    entire cache file. Caching is handled by the calling route.
    """
    with cache_lock:
        if link in THUMBNAIL_CACHE:
            return THUMBNAIL_CACHE[link]
    
    # This part runs if not in cache (outside the lock to allow parallel fetches)
    thumb_url = "https://via.placeholder.com/320x180?text=No+Thumbnail"
    try:
        response = http_session.get(link, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        thumb_tag = soup.find("meta", property="og:image")
        if thumb_tag and thumb_tag.get("content"):
            thumb_url = thumb_tag.get("content")
    except requests.exceptions.RequestException as e:
        logging.warning(f"Thumbnail fetch failed for {link}: {e}")

    # Cache the result in memory
    with cache_lock:
        THUMBNAIL_CACHE[link] = thumb_url
        
    return thumb_url

def load_cache():
    global THUMBNAIL_CACHE
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            try: THUMBNAIL_CACHE = json.load(f)
            except json.JSONDecodeError: THUMBNAIL_CACHE = {}
    logging.info(f"Loaded {len(THUMBNAIL_CACHE)} thumbnail items from cache.")

def save_cache():
    # This should only be called within a cache_lock context
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(THUMBNAIL_CACHE, f)

def parse_videos():
    videos = []
    if not os.path.exists(VIDEO_FILE): return []
    with open(VIDEO_FILE, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().rsplit(' | ', 2)
            if len(parts) == 3:
                title, tags_str, link = parts
                videos.append({"title": title, "tags": [tag.strip() for tag in tags_str.split(',')], "link": link})
            else:
                logging.warning(f"Skipping malformed line: {line.strip()}")
    videos.reverse() # Show newest first
    return videos

# --- FLASK ROUTES ---

@video_bp.route("/videos")
def get_videos():
    """
    FIXED: Now saves the thumbnail cache only ONCE after all parallel fetches are complete.
    """
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 50, type=int)
    query = request.args.get('q', '', type=str).lower().strip()

    all_videos = parse_videos()
    
    filtered_videos = all_videos
    if query:
        search_terms = query.split()
        filtered_videos = [
            v for v in all_videos 
            if all(
                term in v['title'].lower() or any(term in tag.lower() for tag in v['tags'])
                for term in search_terms
            )
        ]

    total_filtered = len(filtered_videos)
    start = (page - 1) * limit
    end = start + limit
    paginated_videos = filtered_videos[start:end]

    def fetch_thumb_for_video(video):
        video['thumb'] = get_or_generate_thumbnail(video['link'])
        return video

    with ThreadPoolExecutor(max_workers=10) as executor:
        enriched_videos = list(executor.map(fetch_thumb_for_video, paginated_videos))

    # After all threads are done, save the potentially updated cache once.
    with cache_lock:
        save_cache()

    return jsonify({
        "videos": enriched_videos,
        "total": total_filtered,
        "page": page,
        "limit": limit
    })


@video_bp.route("/thumbnail", methods=["POST"])
def get_thumbnail_route():
    """Kept for potential single-use cases or backward compatibility."""
    data = request.json
    link = data.get("link")
    if not link:
        return jsonify({"error": "Missing link"}), 400
    thumb_url = get_or_generate_thumbnail(link)
    # Optionally save cache here if this route is used frequently for new items
    with cache_lock:
        save_cache()
    return jsonify({"link": link, "thumb": thumb_url})

@video_bp.route("/add", methods=["POST"])
def add_video():
    """
    FIXED: Now saves the thumbnail cache only ONCE after all new videos are added.
    """
    data = request.json
    urls = data.get("urls")
    if not urls or not isinstance(urls, list):
        return jsonify({"error": "A list of URLs is required."}), 400
    
    results = []
    any_success = False
    existing_links = {v['link'] for v in parse_videos()}

    with open(VIDEO_FILE, "a", encoding="utf-8") as f:
        for url in urls:
            if url in existing_links:
                results.append({"status": "duplicate", "url": url})
                continue
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
    
    # If any videos were successfully added and their thumbnails cached, save the file.
    if any_success:
        with cache_lock:
            save_cache()

    return jsonify(results), 201

@video_bp.route("/remove", methods=["DELETE"])
def remove_video():
    data = request.json
    link_to_remove = data.get("link")
    if not link_to_remove: return jsonify({"error": "Missing link"}), 400
    if not os.path.exists(VIDEO_FILE): return jsonify({"error": "Video file not found."}), 404
    
    lines_to_keep, removed = [], False
    with open(VIDEO_FILE, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().rsplit(' | ', 2)
            if len(parts) == 3 and parts[2] == link_to_remove:
                removed = True
            else:
                lines_to_keep.append(line)
    
    if not removed: return jsonify({"error": "Video not found in file."}), 404
    
    with open(VIDEO_FILE, "w", encoding="utf-8") as f:
        f.writelines(lines_to_keep)
        
    with cache_lock:
        if link_to_remove in THUMBNAIL_CACHE:
            del THUMBNAIL_CACHE[link_to_remove]
            save_cache()
            
    return jsonify({"message": "Video removed successfully."}), 200