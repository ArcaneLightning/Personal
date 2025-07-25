import requests
import time
import json
import os
import threading
import html
import praw
import configparser
from bs4 import BeautifulSoup

# --- Configuration ---
DATA_FILE = "reddit_gallery.json"

# --- PRAW Authentication ---
def authenticate_reddit():
    """Reads config.ini and returns an authenticated PRAW instance."""
    print("\nAuthenticating with Reddit...")
    try:
        config = configparser.ConfigParser()
        config.read('config.ini')
        
        reddit = praw.Reddit(
            client_id=config['reddit']['client_id'],
            client_secret=config['reddit']['client_secret'],
            user_agent=config['reddit']['user_agent'],
            username=config['reddit']['username'],
            password=config['reddit']['password']
        )
        # Validate authentication
        print(f"Successfully authenticated as u/{reddit.user.me()}.")
        return reddit
    except Exception as e:
        print(f"Failed to authenticate. Please check your config.ini file. Error: {e}")
        return None

# --- RedGifs Token Management ---
redgifs_token = { "token": None, "expiry": 0 }

def get_redgifs_token():
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

# --- Data Handling ---
def load_data():
    if not os.path.exists(DATA_FILE): return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except (json.JSONDecodeError, IOError): return []

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f: json.dump(data, f, indent=4)

def scrape_reddit_post(submission, rg_token):
    """
    Processes a PRAW submission object to extract media URLs.
    """
    try:
        media_source_data = submission
        if hasattr(submission, 'crosspost_parent_list'):
            parent_id = submission.crosspost_parent.split('_')[1]
            media_source_data = submission._reddit.submission(id=parent_id)

        results, media_url, media_type = [], None, "image"

        is_redgifs = media_source_data.domain == 'redgifs.com'

        if media_source_data.is_video:
            media_url = media_source_data.media['reddit_video']['fallback_url']
            media_type = "video"
        elif hasattr(media_source_data, 'is_gallery') and media_source_data.is_gallery:
            for item in media_source_data.gallery_data['items']:
                media_id = item['media_id']
                meta = media_source_data.media_metadata[media_id]
                extension = meta['m'].split('/')[-1]
                img_url = f"https://i.redd.it/{media_id}.{extension}"
                results.append({"id": f"{submission.id}_{media_id}", "title": submission.title, "author": str(submission.author), "subreddit": str(submission.subreddit), "media_url": img_url, "type": "image", "source_url": submission.permalink})
            return results, None
        elif 'imgur.com' in media_source_data.domain:
            imgur_url = media_source_data.url
            if imgur_url.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                media_url = imgur_url
            elif imgur_url.endswith('.gifv'):
                media_url = imgur_url.replace('.gifv', '.mp4')
                media_type = "video"
            else:
                try:
                    imgur_res = requests.get(imgur_url, headers={"User-Agent": "MyGallery/2.0"}, timeout=10)
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
            gif_id = media_source_data.url.split('/')[-1]
            api_url = f"https://api.redgifs.com/v2/gifs/{gif_id}"
            try:
                rg_res = requests.get(api_url, headers={"Authorization": f"Bearer {rg_token}"}, timeout=10)
                rg_res.raise_for_status()
                rg_data = rg_res.json()
                media_url = rg_data.get('gif', {}).get('urls', {}).get('hd')
                if media_url: media_type = "video"
                else: return [], "Could not parse 'hd' URL from RedGifs API response."
            except Exception as e:
                return [], f"Failed to get RedGifs URL: {e}"
        elif media_source_data.is_self and media_source_data.selftext_html:
            html_content = html.unescape(media_source_data.selftext_html)
            soup = BeautifulSoup(html_content, 'html.parser')
            img_tag = soup.find('img')
            if img_tag and img_tag.get('src'):
                src = img_tag['src']
                clean_url = src.split('?')[0]
                if clean_url.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    media_url, media_type = clean_url, "image"
        
        if not media_url:
            post_link = media_source_data.url
            if post_link:
                clean_url = post_link.split('?')[0]
                if clean_url.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    media_url, media_type = clean_url, "image"
                elif clean_url.endswith(('.mp4', '.gifv')):
                    media_url, media_type = clean_url.replace('.gifv', '.mp4'), "video"
        
        if not media_url:
            return [], "Unsupported media type or URL not found."

        results.append({"id": submission.id, "title": submission.title, "author": str(submission.author), "subreddit": str(submission.subreddit), "media_url": media_url, "type": media_type, "source_url": submission.permalink})
        return results, None
    except Exception as e:
        return [], f"An error occurred while processing post {submission.id}: {str(e)}"

def run_scraper_for_subreddit(reddit, subreddit_name, target_count, existing_ids, rg_token, nsfw_only):
    print(f"\n{'='*15}\nScraping r/{subreddit_name} for {target_count} new posts...\n{'='*15}")
    new_items_for_this_sub = []
    new_posts_found_count = 0
    
    try:
        subreddit = reddit.subreddit(subreddit_name)
        
        # --- CORRECTED LOGIC: Use different methods for NSFW-only vs. All ---
        post_iterator = None
        if nsfw_only:
            print("\nUsing deep search to find ONLY NSFW posts...")
            query = 'nsfw:yes'
            # Use search() to look through the entire subreddit history
            post_iterator = subreddit.search(query, sort='new', limit=None)
        else:
            print("\nSearching for ALL new posts (SFW and NSFW)...")
            # Use new() to get the latest posts in a standard listing
            post_iterator = subreddit.new(limit=1000)

        for submission in post_iterator:
            if new_posts_found_count >= target_count:
                print(f"Target of {target_count} new posts reached.")
                break

            if submission.id in existing_ids:
                continue
            
            # This check is redundant if nsfw_only is true because of the query,
            # but it's good practice to keep it. It does nothing if nsfw_only is false.
            if nsfw_only and not submission.over_18:
                continue

            print(f"  + New post found: '{submission.title[:40]}...'.")
            items_from_post, error = scrape_reddit_post(submission, rg_token)
            
            if error:
                print(f"      - Could not process post: {error}")
            else:
                new_posts_found_count += 1
                print(f"      -> Progress: {new_posts_found_count} / {target_count} posts found.")
                for item in items_from_post:
                    if item['id'] not in existing_ids:
                        new_items_for_this_sub.append(item)
                        existing_ids.add(item['id'])

    except Exception as e:
        print(f"An error occurred while fetching posts from r/{subreddit_name}: {e}")
    
    if new_posts_found_count < target_count:
        print(f"\nScraping finished for r/{subreddit_name}. Found {new_posts_found_count} new posts (the target was {target_count}).")

    return new_items_for_this_sub

def main():
    reddit = authenticate_reddit()
    if not reddit:
        return

    while True:
        subreddits_input = input("Enter one or more subreddits (separated by space): ").strip()
        if not subreddits_input:
            print("Please enter at least one subreddit.")
            continue
        
        subreddits = [sub.strip() for sub in subreddits_input.split()]
        
        try:
            target_count = int(input(f"How many new posts to find from EACH subreddit? "))
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
        for subreddit_name in subreddits:
            new_items = run_scraper_for_subreddit(reddit, subreddit_name, target_count, existing_ids, rg_token, nsfw_only)
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