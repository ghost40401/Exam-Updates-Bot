import requests
from bs4 import BeautifulSoup
import json
import os
from urllib.parse import urljoin
from datetime import datetime

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
if not DISCORD_WEBHOOK:
    raise RuntimeError("DISCORD_WEBHOOK not set")

DATA_FILE = "posted.json"

SITES = {
    "JEE Main": "https://jeemain.nta.nic.in/Downloads/",
    "NEET": "https://neet.nta.nic.in/Downloads/",
    "ICAI BOS": "https://www.icai.org/category/bos-important-announcements/",
    "ICAI Foundation": "https://www.icai.org/category/foundation-course/",
    "ICAI Intermediate": "https://www.icai.org/category/intermediate-course/",
    "ICAI Final": "https://www.icai.org/category/final-course/"
}

try:
    with open(DATA_FILE, "r") as f:
        posted = json.load(f)
except:
    posted = {}

def send(title, url, source, date=None):
    desc = f"Source: {source}"
    if date:
        desc += f"\nPublished: {date}"

    payload = {
        "embeds": [{
            "title": title,
            "url": url,
            "description": desc,
            "color": 5793266
        }]
    }

    print(f"[POST] {title}")
    requests.post(DISCORD_WEBHOOK, json=payload)

def clean_title(url):
    name = url.split("/")[-1]
    return name.replace("_", " ").replace(".pdf", "").strip()

for name, page in SITES.items():
    print(f"[SCAN] {name}")
    try:
        r = requests.get(page, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"[ERROR] {name}: {e}")
        continue

    pdfs = set()

    for a in soup.select("a[href$='.pdf'], a[href*='/wp-content/uploads/']"):
        pdfs.add(urljoin(page, a["href"]))

    print(f"[FOUND] {len(pdfs)} PDFs")

    for pdf in pdfs:
        if pdf in posted.get(name, []):
            continue

        title = clean_title(pdf)

        try:
            head = requests.head(pdf, timeout=10)
            date = head.headers.get("Last-Modified")
            if date:
                date = datetime.strptime(date, "%a, %d %b %Y %H:%M:%S %Z").strftime("%d-%m-%Y")
        except:
            date = None

        send(title, pdf, name, date)
        posted.setdefault(name, []).append(pdf)

with open(DATA_FILE, "w") as f:
    json.dump(posted, f, indent=2)

print("[DONE]")
