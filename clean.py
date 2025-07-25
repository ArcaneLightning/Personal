# clean_driver_cache.py

import shutil
from pathlib import Path
import os

def clean_cache():
    """
    Finds and deletes the webdriver-manager cache folder to resolve driver issues.
    """
    # The default cache path for webdriver-manager is ~/.wdm
    cache_path = Path.home() / ".wdm"

    print(f"Attempting to clear WebDriver cache at: {cache_path}")

    if cache_path.exists() and cache_path.is_dir():
        try:
            shutil.rmtree(cache_path)
            print("✅ Cache cleared successfully.")
            print("The correct driver will be re-downloaded the next time you run a scraper.")
        except OSError as e:
            print(f"❌ Error clearing cache: {e}")
            print("If this fails, please try deleting the '.wdm' folder in your user directory manually.")
    else:
        print("Cache folder not found (this is normal if it's your first time).")

if __name__ == "__main__":
    clean_cache()