from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import json
import os
import time
import threading
import html
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)

DATA_FILE = "cleaned_data.json"

# --- Rate Limit & Token Management ---
rate_limit_status = {
    "remaining": 100, "reset_time": time.time() + 600, "lock": threading.Lock()
}
redgifs_token = { "token": None, "expiry": 0 }

def get_redgifs_token():
    if redgifs_token["token"] and time.time() < redgifs_token["expiry"] - 60:
        return redgifs_token["token"]
    print("       - Fetching new RedGifs API token...")
    try:
        res = requests.get("https://api.redgifs.com/v2/auth/temporary")
        res.raise_for_status()
        data = res.json()
        redgifs_token["token"] = data.get("token")
        redgifs_token["expiry"] = data.get("expires_at", 0)
        if not redgifs_token["token"]: return None
        print("       - New RedGifs token acquired.")
        return redgifs_token["token"]
    except requests.RequestException as e:
        print(f"       - Could not get RedGifs token: {e}")
        return None

def update_rate_limit_status(headers):
    with rate_limit_status['lock']:
        if 'x-ratelimit-remaining' in headers:
            rate_limit_status['remaining'] = float(headers['x-ratelimit-remaining'])
        if 'x-ratelimit-reset' in headers:
            rate_limit_status['reset_time'] = time.time() + int(headers['x-ratelimit-reset'])

def check_and_wait_for_rate_limit():
    with rate_limit_status['lock']:
        if rate_limit_status['remaining'] < 15:
            wait_duration = rate_limit_status['reset_time'] - time.time()
            if wait_duration > 0:
                print(f"\n[RATE LIMIT] Proactively waiting for {wait_duration + 1:.0f}s...")
                time.sleep(wait_duration + 1)

# --- Data Handling ---
def load_data():
    if not os.path.exists(DATA_FILE): return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except (json.JSONDecodeError, IOError): return []

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f: json.dump(data, f, indent=4)

def scrape_reddit_post(post_url):
    if not post_url.endswith('.json'): post_url += ".json"
    check_and_wait_for_rate_limit()
    try:
        headers = {"User-Agent": "MyGallery/1.0"}
        response = requests.get(post_url, headers=headers, timeout=15)
        update_rate_limit_status(response.headers)
        response.raise_for_status()
        data = response.json()
        crosspost_data = data[0]['data']['children'][0]['data']
        media_source_data = crosspost_data
        if crosspost_data.get('crosspost_parent_list'):
            media_source_data = crosspost_data['crosspost_parent_list'][0]

        results, media_url, media_type = [], None, "image"

        # --- Subreddit Normalization (Write Time) ---
        clean_name = crosspost_data.get('subreddit_name_prefixed', '').split('/')[-1]
        normalized_subreddit = f"r/{clean_name}"

        if 'imgur.com' in media_source_data.get('domain', ''):
            imgur_url = media_source_data.get('url_overridden_by_dest')
            if not imgur_url: return [], "Could not find Imgur URL in post data."
            
            if imgur_url.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                media_url = imgur_url
            elif imgur_url.endswith('.gifv'):
                media_url = imgur_url.replace('.gifv', '.mp4')
                media_type = "video"
            else: # It's a page/album link, scrape it
                try:
                    imgur_res = requests.get(imgur_url, headers=headers, timeout=10)
                    imgur_soup = BeautifulSoup(imgur_res.text, "html.parser")
                    video_tag = imgur_soup.select_one('meta[property="og:video"]')
                    if video_tag and video_tag.get('content'):
                        media_url = video_tag['content']
                        media_type = "video"
                    else:
                        image_tag = imgur_soup.select_one('meta[property="og:image"]')
                        if image_tag and image_tag.get('content'):
                            media_url = image_tag['content'].split('?')[0]
                except Exception as e:
                    return [], f"Failed to scrape Imgur page: {e}"
        
        elif media_source_data.get('domain') == 'redgifs.com':
            token = get_redgifs_token()
            if not token: return [], "Failed to get RedGifs auth token."
            redgifs_url = media_source_data.get('url_overridden_by_dest')
            if redgifs_url:
                gif_id = redgifs_url.split('/')[-1]
                api_url = f"https://api.redgifs.com/v2/gifs/{gif_id}"
                try:
                    auth_headers = {"Authorization": f"Bearer {token}"}
                    rg_res = requests.get(api_url, headers=auth_headers, timeout=10)
                    rg_data = rg_res.json()
                    media_url = rg_data['gif']['urls']['hd']
                    media_type = "video"
                except Exception: return [], "Failed to get RedGifs URL after auth."
        
        elif media_source_data.get('is_gallery', False):
            gallery_items = media_source_data.get('gallery_data', {}).get('items', [])
            media_metadata = media_source_data.get('media_metadata', {})
            for item in gallery_items:
                media_id = item.get('media_id')
                meta = media_metadata.get(media_id)
                if not meta: continue
                extension = meta.get('m', 'image/jpeg').split('/')[-1]
                gallery_media_url = f"https://i.redd.it/{media_id}.{extension}"
                results.append({"id": f"{crosspost_data['id']}_{media_id}", "title": crosspost_data['title'], "author": crosspost_data['author'], "subreddit": normalized_subreddit, "media_url": gallery_media_url, "type": "image", "source_url": crosspost_data['permalink']})
            return results, None

        elif media_source_data.get('is_self') and media_source_data.get('selftext_html'):
            html_content = html.unescape(media_source_data['selftext_html'])
            soup = BeautifulSoup(html_content, 'html.parser')
            link_tag = soup.find('a')
            if link_tag and link_tag.get('href'):
                href = link_tag['href']
                clean_url = href.split('?')[0]
                if clean_url.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    media_url = clean_url
                    media_type = "image"
        
        else:
            if media_source_data.get('is_video', False) and media_source_data.get('secure_media', {}).get('reddit_video'):
                media_url, media_type = media_source_data['secure_media']['reddit_video']['fallback_url'], "video"
            elif 'url_overridden_by_dest' in media_source_data and media_source_data['url_overridden_by_dest'].endswith(('.jpg', '.jpeg', '.png', '.gif')):
                 media_url = media_source_data['url_overridden_by_dest']
        
        if not media_url: return [], "Could not find a direct link to a supported media type."
        
        results.append({
            "id": crosspost_data['id'], "title": crosspost_data['title'], "author": crosspost_data['author'],
            "subreddit": normalized_subreddit, "media_url": media_url,
            "type": media_type, "source_url": crosspost_data['permalink']
        })
        return results, None
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            print("       - Hit rate limit unexpectedly. Waiting 60s...")
            time.sleep(60)
            return scrape_reddit_post(post_url)
        return [], f"HTTP Error: {e}"
    except Exception as e:
        return [], f"An error occurred: {str(e)}"

@app.route("/reddit-gallery/subreddits", methods=["GET"])
def get_subreddits():
    """Lightweight endpoint to get a sorted list of unique subreddits."""
    all_items = load_data()
    # Normalize each subreddit to the "r/name" format before creating a unique set.
    subreddits = sorted(list({
        f"r/{item.get('subreddit', '').split('/')[-1]}"
        for item in all_items if item.get("subreddit")
    }))
    return jsonify(subreddits)

@app.route("/reddit-gallery", methods=["GET"])
def get_gallery():
    all_items = load_data()
    selected_sub = request.args.get('subreddit', '').strip()
    search_query = request.args.get('q', '').lower().strip()

    if selected_sub:
        # Normalize the stored subreddit name before comparing it to the selection.
        all_items = [
            item for item in all_items 
            if f"r/{item.get('subreddit', '').split('/')[-1]}" == selected_sub
        ]
    if search_query:
        all_items = [item for item in all_items if 
                     search_query in item.get('title', '').lower() or
                     search_query in item.get('author', '').lower() or
                     # Normalize the stored subreddit name before searching.
                     search_query in f"r/{item.get('subreddit', '').split('/')[-1]}".lower()]

    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 50, type=int)
    start = (page - 1) * limit
    end = start + limit
    paginated_items = all_items[start:end]

    # Normalize the subreddit for each item in the final paginated response.
    for item in paginated_items:
        if 'subreddit' in item and item['subreddit']:
            item['subreddit'] = f"r/{item['subreddit'].split('/')[-1]}"

    return jsonify({
        "items": paginated_items, "total": len(all_items),
        "page": page, "limit": limit
    })

@app.route("/reddit-gallery", methods=["POST"])
def add_to_gallery():
    urls = request.json.get("urls")
    if not urls or not isinstance(urls, list): return jsonify({"error": "A list of URLs is required."}), 400
    gallery_data = load_data()
    existing_ids = {item.get('id') for item in gallery_data}
    results, new_items_to_add = [], []
    for url in urls:
        try:
            items_from_post, error = scrape_reddit_post(url)
            if error:
                results.append({"status": "error", "url": url, "reason": error}); continue
            for item in items_from_post:
                if item['id'] in existing_ids:
                    results.append({"status": "duplicate", "url": url, "id": item['id']})
                else:
                    new_items_to_add.append(item)
                    existing_ids.add(item['id'])
                    results.append({"status": "success", "title": item['title']})
        except Exception as e:
            results.append({"status": "error", "url": url, "reason": str(e)})
    if new_items_to_add:
        save_data(new_items_to_add + gallery_data)
    return jsonify(results), 201

@app.route("/reddit-gallery", methods=["DELETE"])
def remove_from_gallery():
    item_id = request.json.get("id")
    if not item_id: return jsonify({"error": "Item ID is missing."}), 400
    gallery_data = load_data()
    updated_data = [item for item in gallery_data if item.get("id") != item_id]
    if len(updated_data) == len(gallery_data): return jsonify({"error": "Item not found."}), 404
    save_data(updated_data)
    return jsonify({"message": "Item removed successfully."}), 200

if __name__ == "__main__":
    app.run(debug=True, port=5002)