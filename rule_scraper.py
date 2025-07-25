# rule34_scraper.py

import time
import re
import multiprocessing
import os
from gallery import save_data, load_data

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

BASE_URL = "https://rule34.xxx"
MAX_WORKERS = 2 

def create_driver():
    """Initializes and returns a new Selenium WebDriver instance."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # Suppress webdriver-manager logs
    log_path = os.devnull
    service = Service(ChromeDriverManager().install(), log_path=log_path)
    return webdriver.Chrome(service=service, options=chrome_options)

def worker_scrape_task(url):
    """
    This function runs in a separate process to scrape one URL.
    """
    driver = None
    try:
        driver = create_driver()
        driver.get(url)
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#gelcomVideoPlayer, #image")))
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        media_url, media_type = None, "image"
        video_element = soup.select_one("#gelcomVideoPlayer source")
        if video_element:
            media_url, media_type = video_element.get("src"), "video"
        else:
            image_element = soup.select_one("#image")
            if image_element:
                media_url = image_element.get("src")

        if not media_url:
            return None

        tags = []
        tag_container = soup.select_one("#tag-sidebar")
        if tag_container:
            tag_list_items = tag_container.select('li[class*="tag-type-"]')
            for item in tag_list_items:
                links = item.find_all("a")
                if len(links) > 1:
                    tag_text = links[1].text.strip()
                    if tag_text:
                        tags.append(tag_text.replace(" ", "_"))
        
        post_id_match = re.search(r"id=(\d+)", url)
        if not post_id_match:
            return None

        return {
            "id": post_id_match.group(1), "media_url": media_url, "type": media_type,
            "tags": sorted(list(set(tags))), "source_url": url
        }
    except Exception as e:
        # We don't print here to avoid cluttering the progress bar
        return None
    finally:
        if driver:
            driver.quit()

def main_scraper():
    # --- UPDATED: Handle multiple tags ---
    tags_input = input("Enter one or more tags (separated by space): ").lower().strip()
    # Split by space and join with '+' for the URL format
    tag_query = "+".join(tags_input.split())

    try:
        target_count = int(input("How many NEW posts do you want to find? (e.g., 50): "))
        if target_count <= 0: raise ValueError()
    except ValueError:
        print("Invalid number. Please enter a positive integer.")
        return

    print("Loading existing gallery data...")
    gallery_data = load_data()
    existing_ids = {item.get("id") for item in gallery_data}
    print(f"Found {len(existing_ids)} existing items.")
    
    urls_to_scrape = []
    page_num = 0
    driver = create_driver()
    print("\n--- Phase 1: Finding new post URLs ---")
    try:
        while len(urls_to_scrape) < target_count:
            page_offset = page_num * 42
            # Use the correctly formatted tag query
            search_url = f"{BASE_URL}/index.php?page=post&s=list&tags={tag_query}&pid={page_offset}"
            print(f"Scanning page {page_num + 1}...")
            
            driver.get(search_url)
            soup = BeautifulSoup(driver.page_source, "html.parser")
            post_thumbnails = soup.select("span.thumb > a")
            
            if not post_thumbnails:
                print("No more posts found for this tag combination.")
                break

            for thumb in post_thumbnails:
                post_href = thumb.get("href")
                if not post_href: continue
                post_id_match = re.search(r"id=(\d+)", post_href)
                if not post_id_match: continue
                post_id = post_id_match.group(1)

                if post_id not in existing_ids:
                    full_url = f"{BASE_URL}{post_href}"
                    if full_url not in urls_to_scrape:
                        urls_to_scrape.append(full_url)
                        print(f"  - Queued new post: {post_id} ({len(urls_to_scrape)} / {target_count})")
                
                if len(urls_to_scrape) >= target_count: break
            
            if len(urls_to_scrape) >= target_count: break
            page_num += 1
            time.sleep(1)
    finally:
        driver.quit()

    if not urls_to_scrape:
        print("\nNo new items to scrape.")
        return

    # --- Phase 2: Process the gathered URLs with a progress indicator ---
    print(f"\n--- Phase 2: Scraping details for {len(urls_to_scrape)} new posts using {MAX_WORKERS} workers ---")
    
    new_items_found = []
    total_to_scrape = len(urls_to_scrape)
    
    # Use pool.imap_unordered to get results as they are completed
    with multiprocessing.Pool(processes=MAX_WORKERS) as pool:
        results_iterator = pool.imap_unordered(worker_scrape_task, urls_to_scrape)
        
        for i, result in enumerate(results_iterator):
            if result:
                new_items_found.append(result)
            
            # Print the progress on a single, updating line
            print(f"  -> Progress: {i + 1} / {total_to_scrape} posts processed.", end='\r')

    print("\n") # Add a newline to move past the progress bar

    # --- Step 3: Save the results ---
    if new_items_found:
        print(f"Scraping complete. Successfully scraped {len(new_items_found)} new items.")
        updated_gallery_data = new_items_found + gallery_data
        save_data(updated_gallery_data)
        print("New items have been added to gallery_data.json.")
    else:
        print("Scraping complete, but failed to retrieve details for any new items.")

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main_scraper()
