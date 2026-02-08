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
BASELINE_START = datetime(2025, 10, 1)

SOURCES = [
    {
        "name": "JEE Main",
        "url": "https://jeemain.nta.nic.in/",
        "org": "NTA",
        "exam": "JEE MAIN",
        "emoji": "🪛",
        "type": "NTA",
        "selector": "div[id='1648447930282-deb48cc0-95ec']",
        "menu_id": "li[id='menu-item-6563']"
    },
    {
        "name": "NEET",
        "url": "https://neet.nta.nic.in/",
        "org": "NTA",
        "exam": "NEET",
        "emoji": "🩺",
        "type": "NTA",
        "selector": "div[id='1648449005032-46466f25-2ebe']",
        "menu_id": "li[id='menu-item-6563']"
    },
    {
        "name": "ICAI BOS",
        "url": "https://www.icai.org/category/bos-important-announcements/",
        "org": "ICAI",
        "exam": "IMPORTANT",
        "emoji": "🚨",
        "type": "ICAI"
    },
    {
        "name": "ICAI Foundation",
        "url": "https://www.icai.org/category/foundation-course/",
        "org": "ICAI",
        "exam": "CA FOUNDATION",
        "emoji": "📘",
        "type": "ICAI"
    },
    {
        "name": "ICAI Intermediate",
        "url": "https://www.icai.org/category/intermediate-course/",
        "org": "ICAI",
        "exam": "CA INTERMEDIATE",
        "emoji": "📗",
        "type": "ICAI"
    },
    {
        "name": "ICAI Final",
        "url": "https://www.icai.org/category/final-course/",
        "org": "ICAI",
        "exam": "CA FINAL",
        "emoji": "📕",
        "type": "ICAI"
    },
    {
        "name": "ICAI Main",
        "url": "https://www.icai.org/category/announcements/",
        "org": "ICAI",
        "exam": "ANNOUNCEMENT",
        "emoji": "📢",
        "type": "ICAI"
    }
]

def load_state():
    """Safely loads state, handling migration from old dict format to list."""
    if not os.path.exists(STATE_FILE):
        return []
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
            
            # Legacy Dictionary Format
            if isinstance(data, dict):
                # Safety: Ensure 'posted' exists and is a dict
                posted = data.get("posted")
                if isinstance(posted, dict):
                    return posted.get("_global", [])
                return []
            
            # New List Format
            if isinstance(data, list):
                return data
                
            return []
    except Exception as e:
        print(f"Warning: Could not load state file ({e}). Starting fresh.")
        return []

def save_state(posted_urls):
    with open(STATE_FILE, "w") as f:
        json.dump(posted_urls, f, indent=2)

def extract_date(text):
    if not text:
        return None
    # Enhanced patterns to catch (DD-MM-YYYY) and other variations
    patterns = [
        (r'\(\d{2}-\d{2}-\d{4}\)', "%d-%m-%Y"),  # (04-12-2025)
        (r'\(\d{2}/\d{2}/\d{4}\)', "%d/%m/%Y"),  # (04/12/2025)
        (r'\d{2}-\d{2}-\d{4}', "%d-%m-%Y"),      # 04-12-2025
        (r'\d{2}/\d{2}/\d{4}', "%d/%m/%Y"),      # 04/12/2025
        (r'\d{1,2}\s+[A-Za-z]+\s+\d{4}', "%d %B %Y"), # 4 December 2025
        (r'\d{1,2}\s+[A-Za-z]{3}\s+\d{4}', "%d %b %Y") # 4 Dec 2025
    ]
    for pat, fmt in patterns:
        match = re.search(pat, text)
        if match:
            clean_str = match.group(0).replace('(', '').replace(')', '').strip()
            try:
                return datetime.strptime(clean_str, fmt)
            except ValueError:
                continue
    return None

def process_link(link_element, source, candidates_list):
    try:
        url_suffix = link_element.get_attribute("href")
        text = link_element.inner_text().strip()
        
        if not url_suffix or not text:
            return

        # Noise Filter: Skip breadcrumbs and nav links
        noise_words = ["home", "students", "announcements", "contact", "sitemap"]
        if text.lower() in noise_words:
            return

        full_url = urljoin(source['url'], url_suffix)
        
        if "javascript" in full_url.lower():
            return

        date_obj = extract_date(text)
        
        candidates_list.append({
            "url": full_url,
            "title": text,
            "date": date_obj,
            "source": source
        })
    except:
        pass

def scrape_nta(page, source):
    candidates = []
    print(f"[{source['name']}] Navigating...")
    
    try:
        # Increase timeout to 90s for slow NTA servers
        page.goto(source['url'], timeout=90000, wait_until='domcontentloaded')
    except Exception as e:
        print(f"Error loading {source['name']}: {e}")
        return []

    # --- PART 1: Public Notices ---
    try:
        page.wait_for_selector(source['selector'], timeout=30000)
        container = page.locator(source['selector'])
        notice_links = container.locator("a").all()
        for link in notice_links:
            process_link(link, source, candidates)
    except Exception as e:
        print(f"[{source['name']}] Public Notice section skipped/error: {e}")

    # --- PART 2: Information Dropdown ---
    if source.get('menu_id'):
        try:
            menu_selector = source['menu_id']
            page.wait_for_selector(menu_selector, state="attached", timeout=10000)
            menu_item = page.locator(menu_selector)
            
            if menu_item.count() > 0:
                try:
                    menu_item.hover(timeout=5000)
                except:
                    pass 

                dropdown_links = menu_item.locator("a").all()
                for link in dropdown_links:
                    process_link(link, source, candidates)
        except Exception as e:
            print(f"[{source['name']}] Menu scraping skipped: {e}")

    return candidates

def scrape_icai(page, source):
    candidates = []
    print(f"[{source['name']}] Navigating...")
    try:
        page.goto(source['url'], timeout=90000)
        # Narrow selector to list items to reduce noise
        page.wait_for_selector("div.container.mx-3 li a", timeout=30000)
    except:
        return []

    # REMOVE LIMIT: Scan all links to ensure we hit Oct 2025
    posts = page.locator("div.container.mx-3 li a").all()
    
    for post in posts:
        try:
            process_link(post, source, candidates)
        except:
            continue
    return candidates

def post_to_discord(item):
    src = item['source']
    
    if src["exam"] == "IMPORTANT":
        desc = "🚨 **ICAI posted a new important announcement!**"
    elif src["exam"] == "ANNOUNCEMENT":
        desc = "📢 **ICAI posted a new announcement!**"
    else: 
        desc = (
            f"{src['emoji']} **{src['org']} posted a circular for "
            f"{src['exam']}!**"
        )

    embed = {
        "title": item['title'],
        "url": item['url'],
        "description": desc,
        "color": 5793266,
        "footer": {
            "text": "Examination Update"
        }
    }

    if item['date']:
        embed["footer"]["text"] += f" • Published: {item['date'].strftime('%d-%m-%Y')}"
    else:
        embed["footer"]["text"] += " • Date: Not specified"

    try:
        requests.post(DISCORD_WEBHOOK, json={"content": "@everyone", "embeds": [embed]}) 
    except Exception as e:
        print(f"Failed to send webhook: {e}")

def main():
    if not DISCORD_WEBHOOK:
        raise RuntimeError("DISCORD_WEBHOOK not set")

    posted_urls = load_state()
    print(f"Loaded {len(posted_urls)} previously posted URLs.")
    
    all_candidates = []

    with sync_playwright() as p:
        # User-Agent is critical for NTA websites
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        page = context.new_page()

        for source in SOURCES:
            if source['type'] == "NTA":
                all_candidates.extend(scrape_nta(page, source))
            elif source['type'] == "ICAI":
                all_candidates.extend(scrape_icai(page, source))
        
        browser.close()

    # Filter & Sort
    valid_items = []
    seen_urls = set()
    
    for item in all_candidates:
        if item['url'] in posted_urls:
            continue
        if item['url'] in seen_urls:
            continue
        
        seen_urls.add(item['url'])
        
        # Baseline Logic: 
        if item['date'] and item['date'] < BASELINE_START:
            continue
            
        valid_items.append(item)

    # Sort: Oldest -> Newest (None dates at end)
    valid_items.sort(key=lambda x: (x['date'] is None, x['date'] or datetime.max))

    new_count = 0
    for item in valid_items:
        if item['url'] not in posted_urls:
            print(f"Posting: {item['title']}")
            post_to_discord(item)
            posted_urls.append(item['url'])
            new_count += 1
            
    save_state(posted_urls)
    print(f"Done. Posted {new_count} updates.")

if __name__ == "__main__":
    main()
