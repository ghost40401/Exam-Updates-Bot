import requests
from bs4 import BeautifulSoup
import json
from urllib.parse import urljoin
import os

# ===== CONFIG =====
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")  # Read from GitHub Secrets
if not DISCORD_WEBHOOK:
    raise ValueError("DISCORD_WEBHOOK environment variable not set!")

DATA_FILE = "posted.json"

# Websites to track
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
def send_discord(title, url, source):
    embed = {
        "embeds": [{
            "title": title,
            "url": url,
            "description": f"Source: {source}",
            "color": 3447003
        }]
    }
    response = requests.post(DISCORD_WEBHOOK, json=embed)
    if response.status_code != 204:
        print(f"Failed to send {title} - {response.status_code}")

# Scrape each site
for name, base_url in sites.items():
    try:
        res = requests.get(base_url, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
    except Exception as e:
        print(f"Error fetching {name}: {e}")
        continue

    links = []

    # NTA (JEE/NEET) parsing
    if "nta.nic.in" in base_url:
        for a in soup.select("a[href]"):
            text = a.text.strip()
            href = urljoin(base_url, a['href'])
            if text and ("Notification" in text or "Circular" in text or "Update" in text):
                if href.lower().endswith(".pdf"):
                    links.append((text + " (PDF)", href))
                else:
                    links.append((text, href))

    # ICAI parsing
    else:
        for post in soup.select("h3.entry-title a"):
            title = post.text.strip()
            href = urljoin(base_url, post['href'])

            # Check if post contains PDF
            try:
                post_res = requests.get(href, timeout=10)
                post_soup = BeautifulSoup(post_res.text, "html.parser")
                pdf_link = None
                for a in post_soup.select("a[href$='.pdf']"):
                    pdf_link = urljoin(href, a['href'])
                    break  # take first PDF
                if pdf_link:
                    links.append((title + " (PDF)", pdf_link))
                else:
                    links.append((title, href))
            except:
                links.append((title, href))

    # Post new links
    for title, link in links:
        if link not in posted.get(name, []):
            send_discord(title, link, name)
            posted.setdefault(name, []).append(link)

# Save updated posted links
with open(DATA_FILE, "w") as f:
    json.dump(posted, f, indent=2)
