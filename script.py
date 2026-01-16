import requests
from bs4 import BeautifulSoup
import json
from urllib.parse import urljoin
import os
from datetime import datetime

# ===== CONFIG =====
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
if not DISCORD_WEBHOOK:
    raise ValueError("DISCORD_WEBHOOK environment variable not set!")

DATA_FILE = "posted.json"

sites = {
    "JEE Main": "https://jeemain.nta.nic.in/",
    "NEET": "https://neet.nta.nic.in/",
    "ICAI BOS": "https://www.icai.org/category/bos-important-announcements",
    "ICAI Foundation": "https://www.icai.org/category/foundation-course",
    "ICAI Intermediate": "https://www.icai.org/category/intermediate-course",
    "ICAI Final": "https://www.icai.org/category/final-course"
}

# Load already posted links
try:
    with open(DATA_FILE, "r") as f:
        posted = json.load(f)
except FileNotFoundError:
    posted = {}

# Send Discord embed
def send_discord(title, url, source, pub_date=None):
    description = f"Source: {source}"
    if pub_date:
        description += f"\nPublished: {pub_date}"
    embed = {
        "embeds": [{
            "title": title,
            "url": url,
            "description": description,
            "color": 3447003
        }]
    }
    print(f"[DEBUG] Sending to Discord: {title} -> {url}")  # debug print
    response = requests.post(DISCORD_WEBHOOK, json=embed)
    if response.status_code != 204:
        print(f"Failed to send {title} - {response.status_code}")

# Scrape each site
for name, base_url in sites.items():
    print(f"[DEBUG] Checking site: {name} -> {base_url}")  # debug print

    try:
        res = requests.get(base_url, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
    except Exception as e:
        print(f"Error fetching {name}: {e}")
        continue

    links = []

    # NTA (JEE/NEET)
    if "nta.nic.in" in base_url:
        for a in soup.select("a[href]"):
            text = a.text.strip()
            href = urljoin(base_url, a['href'])
            if text and ("Notification" in text or "Circular" in text or "Update" in text):
                # Try to get date from nearby text
                pub_date = None
                parent_text = a.find_parent().text
                if parent_text:
                    for part in parent_text.split():
                        try:
                            dt = datetime.strptime(part, "%d-%m-%Y")
                            pub_date = dt.strftime("%d-%m-%Y")
                            break
                        except:
                            continue
                if href.lower().endswith(".pdf"):
                    links.append((text + " (PDF)", href, pub_date))
                else:
                    links.append((text, href, pub_date))

    # ICAI
    else:
        for post in soup.select("h3.entry-title a"):
            title = post.text.strip()
            href = urljoin(base_url, post['href'])
            pub_date = None
            try:
                post_res = requests.get(href, timeout=10)
                post_soup = BeautifulSoup(post_res.text, "html.parser")
                # Extract date from ICAI post meta
                date_tag = post_soup.select_one("time.entry-date")
                if date_tag:
                    pub_date = date_tag.text.strip()
                # Check PDF in post
                pdf_link = None
                for a in post_soup.select("a[href$='.pdf']"):
                    pdf_link = urljoin(href, a['href'])
                    break
                if pdf_link:
                    links.append((title + " (PDF)", pdf_link, pub_date))
                else:
                    links.append((title, href, pub_date))
            except Exception as e:
                print(f"[DEBUG] Error fetching post {href}: {e}")
                links.append((title, href, pub_date))

    print(f"[DEBUG] Found {len(links)} links on {name}")  # debug print
    for t, l, d in links:
        print(f"[DEBUG] Link: {t} -> {l} | Date: {d}")  # debug print

    # Post new links
    for title, link, pub_date in links:
        if link not in posted.get(name, []):
            send_discord(title, link, name, pub_date)
            posted.setdefault(name, []).append(link)

# Save updated posted links
with open(DATA_FILE, "w") as f:
    json.dump(posted, f, indent=2)
print("[DEBUG] Script finished")  # debug print
