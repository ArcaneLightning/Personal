import requests
import time
import json
import os
import threading
import html
from bs4 import BeautifulSoup

# --- Configuration ---
POST_LIMIT_PER_PAGE = 100
SAFETY_DUPLICATE_THRESHOLD = 1000
DATA_FILE = "reddit_gallery.json"

# --- Self-Contained Rate Limit Handling ---
rate_limit_status = {
    "remaining": 100,
    "reset_time": time.time() + 600,
    "lock": threading.Lock()
}

# --- RedGifs Token Management ---
redgifs_token = {
    "token": None,
    "expiry": 0
}

def get_redgifs_token():
    """
    Fetches a temporary authentication token from the RedGifs API if the current one is invalid or expired.
    """
    if redgifs_token["token"] and time.time() < redgifs_token["expiry"] - 60:
        return redgifs_token["token"]

    print("      - Fetching new RedGifs API token...")
    try:
        res = requests.get("https://api.redgifs.com/v2/auth/temporary")
        res.raise_for_status()
        data = res.json()
        
        redgifs_token["token"] = data.get("token")
        redgifs_token["expiry"] = data.get("expires_at", 0)
        
        if not redgifs_token["token"]:
            print("      - Failed to get token from RedGifs API response.")
            return None
        
        print("      - New RedGifs token acquired.")
        return redgifs_token["token"]
    except requests.RequestException as e:
        print(f"      - Could not get RedGifs token: {e}")
        return None


def update_rate_limit_status(headers):
    """Reads headers and updates the script's rate limit status."""
    with rate_limit_status['lock']:
        if 'x-ratelimit-remaining' in headers:
            rate_limit_status['remaining'] = float(headers['x-ratelimit-remaining'])
        if 'x-ratelimit-reset' in headers:
            reset_seconds = int(headers['x-ratelimit-reset'])
            rate_limit_status['reset_time'] = time.time() + reset_seconds
        
        remaining_time = max(0, rate_limit_status['reset_time'] - time.time())
        print(f"      [Rate Limit Info] Requests remaining: {rate_limit_status['remaining']:.0f}, Resets in: {remaining_time:.0f}s")

def check_and_wait_for_rate_limit():
    """Proactively waits if the request limit is low."""
    with rate_limit_status['lock']:
        if rate_limit_status['remaining'] < 2:
            wait_duration = rate_limit_status['reset_time'] - time.time()
            if wait_duration > 0:
                print(f"\n[RATE LIMIT] Low on requests. Proactively waiting for {wait_duration + 1:.0f} seconds...")
                time.sleep(wait_duration + 1)

# --- Duplicated functions from server to make script standalone ---
def load_data():
    if not os.path.exists(DATA_FILE): return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError): return []

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def scrape_reddit_post(post_url, rg_token):
    """Scrapes a single post, now with its own rate limit handling."""
    if not post_url.endswith('.json'):
        post_url += ".json"
    
    check_and_wait_for_rate_limit()
    
    try:
        headers = {"User-Agent": "MyGallery/1.0"}
        response = requests.get(post_url, headers=headers, timeout=15)
        update_rate_limit_status(response.headers)
        response.raise_for_status()

        data = response.json()
        
        if not data or not data[0].get('data', {}).get('children'):
            return [], "Empty or malformed post data."

        crosspost_data = data[0]['data']['children'][0]['data']
        media_source_data = crosspost_data
        if crosspost_data.get('crosspost_parent_list'):
            media_source_data = crosspost_data['crosspost_parent_list'][0]
        
        results = []
        media_url, media_type = None, "image"
        
        media_info = media_source_data.get('media') or {}
        is_redgifs = 'redgifs.com' in media_source_data.get('domain', '') or \
                     media_info.get('type') == 'redgifs.com'

        if media_source_data.get('is_video', False) and media_source_data.get('secure_media', {}).get('reddit_video'):
            media_url = media_source_data['secure_media']['reddit_video']['fallback_url']
            media_type = "video"

        elif media_source_data.get('is_gallery', False):
            gallery_items = media_source_data.get('gallery_data', {}).get('items', [])
            media_metadata = media_source_data.get('media_metadata', {})
            for item in gallery_items:
                media_id = item.get('media_id')
                meta = media_metadata.get(media_id)
                if not meta: continue
                extension = meta.get('m', 'image/jpeg').split('/')[-1]
                img_url = f"https://i.redd.it/{media_id}.{extension}"
                results.append({"id": f"{crosspost_data['id']}_{media_id}", "title": crosspost_data['title'], "author": crosspost_data['author'], "subreddit": crosspost_data['subreddit_name_prefixed'], "media_url": img_url, "type": "image", "source_url": crosspost_data['permalink']})
            return results, None

        elif 'imgur.com' in media_source_data.get('domain', ''):
            imgur_url = media_source_data.get('url_overridden_by_dest')
            if not imgur_url: return [], "Could not find Imgur URL in post data."
            if imgur_url.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                media_url = imgur_url
            elif imgur_url.endswith('.gifv'):
                media_url = imgur_url.replace('.gifv', '.mp4')
                media_type = "video"
            else:
                try:
                    imgur_res = requests.get(imgur_url, headers=headers, timeout=10)
                    imgur_soup = BeautifulSoup(imgur_res.text, "html.parser")
                    video_tag = imgur_soup.select_one('meta[property="og:video"]')
                    if video_tag and video_tag.get('content'):
                        media_url, media_type = video_tag['content'], "video"
                    else:
                        image_tag = imgur_soup.select_one('meta[property="og:image"]')
                        if image_tag and image_tag.get('content'):
                            media_url = image_tag['content'].split('?')[0]
                except Exception as e:
                    return [], f"Failed to scrape Imgur page: {e}"

        elif is_redgifs:
            if not rg_token: return [], "Missing RedGifs auth token."
            redgifs_url = media_source_data.get('url_overridden_by_dest')
            if redgifs_url:
                gif_id = redgifs_url.split('/')[-1]
                api_url = f"https://api.redgifs.com/v2/gifs/{gif_id}"
                try:
                    auth_headers = {"Authorization": f"Bearer {rg_token}"}
                    rg_res = requests.get(api_url, headers=auth_headers, timeout=10)
                    rg_res.raise_for_status()
                    rg_data = rg_res.json()
                    media_url = rg_data.get('gif', {}).get('urls', {}).get('hd')
                    if media_url:
                        media_type = "video"
                    else:
                        return [], "Could not parse 'hd' URL from RedGifs API response."
                except Exception as e:
                    return [], f"Failed to get RedGifs URL: {e}"
        
        # --- REVISED LOGIC: Look for <img> tag in text posts ---
        elif media_source_data.get('is_self') and media_source_data.get('selftext_html'):
            html_content = html.unescape(media_source_data['selftext_html'])
            soup = BeautifulSoup(html_content, 'html.parser')
            
            img_tag = soup.find('img') # Prioritize finding the <img> tag directly
            if img_tag and img_tag.get('src'):
                src = img_tag['src']
                clean_url = src.split('?')[0]
                if clean_url.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    media_url = clean_url
                    media_type = "image"
        # --- END OF REVISED LOGIC ---
                    
        elif 'url_overridden_by_dest' in media_source_data:
            clean_url = media_source_data['url_overridden_by_dest'].split('?')[0]
            if clean_url.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                media_url = clean_url
            
        if not media_url: 
            # Final fallback: check the main 'url' field for a direct media link.
            post_link = media_source_data.get('url')
            if post_link:
                clean_url = post_link.split('?')[0]
                if clean_url.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    media_url = clean_url
                    media_type = "image"
                elif clean_url.endswith(('.mp4', '.gifv')):
                    media_url = clean_url.replace('.gifv', '.mp4')
                    media_type = "video"

        if not media_url:
            return [], "Unsupported media type or URL not found."
        
        results.append({"id": crosspost_data['id'], "title": crosspost_data['title'], "author": crosspost_data['author'], "subreddit": crosspost_data['subreddit_name_prefixed'], "media_url": media_url, "type": media_type, "source_url": crosspost_data['permalink']})
        
        return results, None
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            print("      - Hit rate limit unexpectedly. Waiting 60s...")
            time.sleep(60)
            return scrape_reddit_post(post_url, rg_token)
        return [], f"HTTP Error: {e}"
    except Exception as e:
        return [], f"An error occurred: {str(e)}"

def run_scraper_for_subreddit(subreddit, target_count, existing_ids, rg_token, nsfw_only):
    """Main scraping logic for a single subreddit."""
    print(f"\n{'='*15}\nScraping r/{subreddit} for {target_count} new posts...\n{'='*15}")
    
    new_items_for_this_sub = []
    new_posts_found_count = 0
    consecutive_duplicates_found = 0
    after_token, page_count = None, 0

    while new_posts_found_count < target_count:
        page_count += 1
        api_url = f"https://www.reddit.com/r/{subreddit}/new.json?limit={POST_LIMIT_PER_PAGE}"
        if after_token:
            api_url += f"&after={after_token}"

        print(f"\n--- Fetching Page {page_count} from r/{subreddit} ---")
        check_and_wait_for_rate_limit()

        try:
            headers = {"User-Agent": "MyGallery/1.0"}
            response = requests.get(api_url, headers=headers, timeout=15)
            update_rate_limit_status(response.headers)
            response.raise_for_status()

            data = response.json()
            posts = data['data']['children']
            if not posts:
                print("No more posts found for this subreddit."); break

            for post in posts:
                post_data = post['data']

                if nsfw_only and not post_data.get('over_18', False):
                    continue

                permalink = post_data['permalink']
                full_url = f"https://www.reddit.com{permalink}"
                
                first_potential_id = post_data.get('id')
                if post_data.get('is_gallery'):
                    gallery_data = post_data.get('gallery_data')
                    if gallery_data and gallery_data.get('items'):
                        try:
                            first_media_id = gallery_data['items'][0]['media_id']
                            first_potential_id = f"{first_potential_id}_{first_media_id}"
                        except (KeyError, IndexError):
                            pass

                if first_potential_id in existing_ids:
                    consecutive_duplicates_found += 1
                else:
                    consecutive_duplicates_found = 0
                    print(f"  + New post found: '{post_data['title'][:40]}...'.")
                    
                    items_from_post, error = scrape_reddit_post(full_url, rg_token)
                    if error:
                        print(f"      - Could not process post: {error}")
                    else:
                        new_posts_found_count += 1
                        print(f"      -> Progress: {new_posts_found_count} / {target_count} posts found.")
                        for item in items_from_post:
                            new_items_for_this_sub.append(item)
                            existing_ids.add(item['id'])
                
                if new_posts_found_count >= target_count: break
            
            after_token = data['data']['after']
            if not after_token or consecutive_duplicates_found >= SAFETY_DUPLICATE_THRESHOLD or new_posts_found_count >= target_count:
                if not after_token: print("\nReached the end of the subreddit's listing.")
                if consecutive_duplicates_found >= SAFETY_DUPLICATE_THRESHOLD: print(f"\nSafety Stop: Found {SAFETY_DUPLICATE_THRESHOLD} consecutive duplicates.")
                break
            
            time.sleep(2)
        
        except requests.exceptions.RequestException as e:
            print(f"An unrecoverable connection error occurred: {e}"); break
    
    return new_items_for_this_sub

def main():
    while True:
        subreddits_input = input("Enter one or more subreddits (separated by space): ").strip()
        if not subreddits_input:
            print("Please enter at least one subreddit.")
            continue
        
        subreddits = [sub.strip() for sub in subreddits_input.split()]
        
        try:
            target_count = int(input(f"How many NEW posts to find from EACH subreddit? "))
            if target_count <= 0: raise ValueError()
        except ValueError:
            print("Invalid number. Please enter a positive integer."); continue

        nsfw_only_input = input("Only scrape NSFW posts? (y/n): ").lower().strip()
        nsfw_only = nsfw_only_input == 'y'

        gallery_data = load_data()
        existing_ids = {item.get("id") for item in gallery_data}
        print(f"\nLoaded {len(existing_ids)} existing items from database.")

        rg_token = get_redgifs_token()

        total_new_items = []
        for subreddit in subreddits:
            new_items = run_scraper_for_subreddit(subreddit, target_count, existing_ids, rg_token, nsfw_only)
            total_new_items.extend(new_items)
        
        if total_new_items:
            print(f"\nScraping session complete. Found a total of {len(total_new_items)} new images/videos.")
            updated_gallery_data = total_new_items + gallery_data
            save_data(updated_gallery_data)
            print("New items have been added to reddit_gallery.json.")
        else:
            print("\nScraping session complete. No new items were found.")
        
        another_run = input("\nScrape more subreddits? (y/n): ").lower()
        if another_run != 'y':
            break

if __name__ == "__main__":
    main()