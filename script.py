import os
import json
import re
import requests
from datetime import datetime
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
STATE_FILE = "posted.json"
# Baseline: 01 October 2025 [cite: 5]
BASELINE_START = datetime(2025, 10, 1)

# Source Definitions 
SOURCES = [
    {
        "name": "JEE Main",
        "url": "https://jeemain.nta.nic.in/",
        "org": "NTA",
        "exam": "JEE MAIN",
        "emoji": "🧪",
        "type": "NTA",
        # Specific DIV ID for Public Notices 
        "selector": "div#1648447930282-deb48cc0-95ec",
        "menu_id": "li#menu-item-6563"
    },
    {
        "name": "NEET",
        "url": "https://neet.nta.nic.in/",
        "org": "NTA",
        "exam": "NEET",
        "emoji": "🩺",
        "type": "NTA",
        # Specific DIV ID for Public Notices 
        "selector": "div#1648449005032-46466f25-2ebe",
        "menu_id": "li#menu-item-6563"
    },
    {
        "name": "ICAI BOS",
        "url": "https://www.icai.org/category/bos-important-announcements/",
        "org": "ICAI",
        "exam": "IMPORTANT", # Trigger for specific msg [cite: 8]
        "emoji": "🚨",
        "type": "ICAI"
    },
    {
        "name": "ICAI Foundation",
        "url": "https://www.icai.org/category/foundation-course/",
        "org": "ICAI",
        "exam": "CA FOUNDATION", # Trigger for specific msg [cite: 10]
        "emoji": "📘",
        "type": "ICAI"
    },
    {
        "name": "ICAI Intermediate",
        "url": "https://www.icai.org/category/intermediate-course/",
        "org": "ICAI",
        "exam": "CA INTERMEDIATE", # Trigger for specific msg [cite: 10]
        "emoji": "📗",
        "type": "ICAI"
    },
    {
        "name": "ICAI Final",
        "url": "https://www.icai.org/category/final-course/",
        "org": "ICAI",
        "exam": "CA FINAL", # Trigger for specific msg [cite: 10]
        "emoji": "📕",
        "type": "ICAI"
    },
    {
        "name": "ICAI Main",
        "url": "https://www.icai.org/category/announcements/",
        "org": "ICAI",
        "exam": "ANNOUNCEMENT", # Trigger for specific msg [cite: 9]
        "emoji": "📢",
        "type": "ICAI"
    }
]

def load_state():
    if not os.path.exists(STATE_FILE):
        return []
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_state(posted_urls):
    with open(STATE_FILE, "w") as f:
        json.dump(posted_urls, f, indent=2)

def extract_date(text):
    """Attempts to parse a date from text string."""
    if not text:
        return None
    # Patterns for dd-mm-yyyy, dd/mm/yyyy, dd Month yyyy
    patterns = [
        (r'\d{2}-\d{2}-\d{4}', "%d-%m-%Y"),
        (r'\d{2}/\d{2}/\d{4}', "%d/%m/%Y"),
        (r'\d{1,2}\s+[A-Za-z]+\s+\d{4}', "%d %B %Y"),
        (r'\d{1,2}\s+[A-Za-z]{3}\s+\d{4}', "%d %b %Y")
    ]
    for pat, fmt in patterns:
        match = re.search(pat, text)
        if match:
            try:
                return datetime.strptime(match.group(0), fmt)
            except ValueError:
                continue
    return None

def scrape_nta(page, source):
    """Scrapes NTA sites: Public Notices AND Information Dropdown."""
    candidates = []
    print(f"[{source['name']}] Navigating...")
    
    try:
        page.goto(source['url'], timeout=60000)
    except Exception as e:
        print(f"Error loading {source['name']}: {e}")
        return []

    # --- PART 1: Public Notices (div container) ---
    try:
        # Wait for the specific Public Notice container
        page.wait_for_selector(source['selector'], timeout=30000)
        container = page.locator(source['selector'])
        notice_links = container.locator("a").all()
        
        for link in notice_links:
            process_link(link, source, candidates)
            
    except Exception as e:
        print(f"[{source['name']}] Public Notice section error: {e}")

    # --- PART 2: Information Dropdown (li menu) ---
    if source.get('menu_id'):
        try:
            menu_selector = source['menu_id']
            menu_item = page.locator(menu_selector)
            
            # Hover to ensure sub-menus are generated/visible in the DOM
            if menu_item.count() > 0:
                menu_item.hover()
                
                # Extract all links inside the dropdown (including sub-items)
                dropdown_links = menu_item.locator("a").all()
                print(f"[{source['name']}] Found {len(dropdown_links)} links in Information menu.")
                
                for link in dropdown_links:
                    process_link(link, source, candidates)
            else:
                print(f"[{source['name']}] Menu selector {menu_selector} not found.")

        except Exception as e:
            print(f"[{source['name']}] Menu scraping error: {e}")

    return candidates

def process_link(link_element, source, candidates_list):
    """Helper to extract data from a link element and add to list."""
    try:
        url_suffix = link_element.get_attribute("href")
        if not url_suffix:
            return

        text = link_element.inner_text().strip()
        full_url = urljoin(source['url'], url_suffix)
        
        # Filter: Ignore javascript:void(0) or empty links
        if "javascript" in full_url.lower() or not text:
            return

        # Attempt to get date from the link text
        date_obj = extract_date(text)
        
        candidates_list.append({
            "url": full_url,
            "title": text,
            "date": date_obj,
            "source": source
        })
    except Exception as e:
        # Silently fail for individual bad links
        pass

def scrape_icai(page, source):
    """Scrapes ICAI announcements list."""
    candidates = []
    print(f"[{source['name']}] Navigating...")
    try:
        page.goto(source['url'], timeout=60000)
        page.wait_for_selector("div.container.mx-3", timeout=30000)
    except:
        return []

    # Get all announcement links in the container
    # ICAI structure: .container.mx-3 -> ul -> li -> a
    posts = page.locator("div.container.mx-3 a").all()
    
    # Limit to first 15 posts to save time (we run hourly)
    for i, post in enumerate(posts[:15]):
        try:
            url = post.get_attribute("href")
            title = post.inner_text().strip()
            full_url = urljoin(source['url'], url)
            
            # ICAI lists usually don't have dates in the main list text
            # We must visit the page to get the date accurately or check the tooltip
            
            date_obj = None
            # Quick visit to the notice page to get real date
            try:
                # Open in new tab or just navigate? Navigation is safer for state.
                # However, for speed, let's extract date from text if possible, 
                # otherwise treat as None (which is allowed) [cite: 3]
                date_obj = extract_date(title)
            except:
                pass

            candidates.append({
                "url": full_url,
                "title": title,
                "date": date_obj,
                "source": source
            })
        except:
            continue
            
    return candidates

def post_to_discord(item):
    """Formats and sends the embed."""
    src = item['source']
    
    # Logic for description [cite: 8, 9, 10]
    if src["exam"] == "IMPORTANT":
        desc = "🚨 **ICAI posted a new important announcement!**"
    elif src["exam"] == "ANNOUNCEMENT":
        desc = "📢 **ICAI posted a new announcement!**"
    elif src["org"] == "ICAI":
        desc = f"**ICAI posted a circular for {src['exam']}!**"
    else:
        # NTA Logic
        desc = f"**NTA posted a circular for {src['exam']}!**"

    embed = {
        "title": item['title'],
        "url": item['url'],
        "description": desc,
        "color": 5793266, # Green-ish
        "footer": {
            "text": "Examination Update"
        }
    }

    # Add date to footer if available [cite: 5]
    if item['date']:
        embed["footer"]["text"] += f" • Published: {item['date'].strftime('%d-%m-%Y')}"
    else:
        embed["footer"]["text"] += " • Date: Not specified"

    payload = {
        "content": "@everyone", # [cite: 6]
        "embeds": [embed]
    }

    try:
        requests.post(DISCORD_WEBHOOK, json=payload)
    except Exception as e:
        print(f"Failed to send Discord webhook: {e}")

def main():
    if not DISCORD_WEBHOOK:
        raise RuntimeError("DISCORD_WEBHOOK is not set.")

    posted_urls = load_state()
    all_candidates = []

    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 1. Collect ALL candidates from ALL sources
        for source in SOURCES:
            if source['type'] == "NTA":
                all_candidates.extend(scrape_nta(page, source))
            elif source['type'] == "ICAI":
                all_candidates.extend(scrape_icai(page, source))
        
        browser.close()

    # 2. Filter & Clean Data
    valid_items = []
    for item in all_candidates:
        # Deduplication check
        if item['url'] in posted_urls:
            continue
        
        # Baseline Check [cite: 5]
        # If date exists, must be >= Baseline.
        # If date is None, INCLUDE it[cite: 3].
        if item['date']:
            if item['date'] < BASELINE_START:
                continue 
        
        valid_items.append(item)

    # 3. Global Sort 
    # Sort key: (Has Date?, Date Value). 
    # Items with dates come first, sorted old->new. 
    # Items without dates come last (or first, depending on preference, 
    # but strictly sorting requires a comparable key).
    # We map None to datetime.max to put them at the end, or min to put at start.
    # Logic: Oldest date -> Newest date.
    
    def sort_key(x):
        d = x['date']
        if d is None:
            # If no date, treat as "now" so it appends at the end?
            # Or treat as very old? 
            # Requirement: "Oldest first". 
            # If we don't know the date, we can't sort it correctly relative to others.
            # We will append them at the end to ensure they are seen.
            return datetime.max 
        return d

    valid_items.sort(key=sort_key)

    # 4. Post and Save
    new_posted_count = 0
    for item in valid_items:
        # Double check duplicate before posting (in case of dupes in source list)
        if item['url'] in posted_urls:
            continue

        print(f"Posting: {item['title']}")
        post_to_discord(item)
        posted_urls.append(item['url'])
        new_posted_count += 1
        
    save_state(posted_urls)
    print(f"Run complete. Posted {new_posted_count} new updates.")

if __name__ == "__main__":
    main()
