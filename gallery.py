# gallery_server.py

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import json
import os
import re

app = Flask(__name__)
CORS(app)

DATA_FILE = "gallery_data.json"

def load_data():
    if not os.path.exists(DATA_FILE): return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError): return []

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def scrape_page(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        media_url, media_type = None, "image"
        video_element = soup.select_one("#gelcomVideoPlayer > source")
        if video_element:
            media_url, media_type = video_element.get("src"), "video"
        else:
            image_element = soup.select_one("#image")
            if image_element:
                media_url = image_element.get("src")
        if not media_url: return None, "Could not find image or video URL."
        tags = []
        tag_container = soup.select_one("#tag-sidebar")
        if tag_container:
            list_items = tag_container.select('li[class*="tag-type-"]')
            for item in list_items:
                links = item.find_all("a")
                if len(links) > 1:
                    second_link = links[1]
                    tag_text = second_link.text.strip()
                    if tag_text:
                        tags.append(tag_text.replace(" ", "_"))
        post_id_match = re.search(r"id=(\d+)", url)
        if not post_id_match: return None, "URL does not contain a valid post ID."
        return {
            "id": post_id_match.group(1), "media_url": media_url, "type": media_type,
            "tags": sorted(list(set(tags))), "source_url": url
        }, None
    except requests.exceptions.RequestException as e:
        return None, str(e)

@app.route("/gallery/tags", methods=["GET"])
def get_all_tags():
    """NEW lightweight endpoint to get a sorted list of all unique tags."""
    all_items = load_data()
    all_tags = set()
    for item in all_items:
        for tag in item.get("tags", []):
            all_tags.add(tag)
    return jsonify(sorted(list(all_tags)))

@app.route("/gallery", methods=["GET"])
def get_gallery():
    all_items = load_data()
    search_query = request.args.get('q', '').lower().strip()
    if search_query:
        query_tags = search_query.split(' ')
        filtered_items = []
        for item in all_items:
            item_tags_lower = {tag.lower() for tag in item.get('tags', [])}
            if all(any(qt in it for it in item_tags_lower) for qt in query_tags):
                filtered_items.append(item)
        all_items = filtered_items
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 50, type=int)
    start = (page - 1) * limit
    end = start + limit
    paginated_items = all_items[start:end]
    return jsonify({
        "items": paginated_items, "total": len(all_items),
        "page": page, "limit": limit
    })

@app.route("/gallery", methods=["POST"])
def add_to_gallery():
    urls = request.json.get("urls")
    if not urls or not isinstance(urls, list): return jsonify({"error": "A list of URLs is required."}), 400
    gallery_data = load_data()
    existing_source_urls = {item['source_url'] for item in gallery_data}
    results, new_items = [], []
    for url in urls:
        if url in existing_source_urls:
            results.append({"status": "duplicate", "url": url})
            continue
        try:
            new_item, error = scrape_page(url)
            if error: raise Exception(error)
            new_items.append(new_item)
            existing_source_urls.add(url)
            results.append({"status": "success", "id": new_item['id']})
        except Exception as e:
            results.append({"status": "error", "url": url, "reason": str(e)})
    if new_items:
        save_data(new_items + gallery_data)
    return jsonify(results), 201

@app.route("/gallery", methods=["DELETE"])
def remove_from_gallery():
    item_id = request.json.get("id")
    if not item_id: return jsonify({"error": "Item ID is missing."}), 400
    gallery_data = load_data()
    updated_data = [item for item in gallery_data if item.get("id") != item_id]
    if len(updated_data) == len(gallery_data): return jsonify({"error": "Item not found."}), 404
    save_data(updated_data)
    return jsonify({"message": "Item removed successfully."}), 200

if __name__ == "__main__":
    app.run(debug=True, port=5001)
