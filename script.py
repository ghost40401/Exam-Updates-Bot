import requests
import json
import os
from bs4 import BeautifulSoup
from datetime import datetime

WEBHOOK_URL = os.environ["DISCORD_WEBHOOK"]
STATE_FILE = "posted.json"
BASELINE_DATE = datetime(2026, 1, 1)

SOURCES = {
    "ICAI Important": {
        "url": "https://www.icai.org/post.html?post_id=important-announcement",
        "org": "ICAI",
        "exam": "IMPORTANT"
    },
    "ICAI Final": {
        "url": "https://www.icai.org/post.html?post_id=final-course",
        "org": "ICAI",
        "exam": "CA FINAL"
    },
    "ICAI Intermediate": {
        "url": "https://www.icai.org/post.html?post_id=intermediate-course",
        "org": "ICAI",
        "exam": "CA INTERMEDIATE"
    },
    "ICAI Foundation": {
        "url": "https://www.icai.org/post.html?post_id=foundation-course",
        "org": "ICAI",
        "exam": "CA FOUNDATION"
    }
}

EXAM_EMOJI = {
    "CA FOUNDATION": "📘",
    "CA INTERMEDIATE": "📗",
    "CA FINAL": "📕",
    "IMPORTANT": "🚨"
}

ORG_EMOJI = {
    "ICAI": "🏛",
    "NTA": "🧪"
}


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def fetch_pdfs(url):
    r = requests.get(url, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")

    results = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith(".pdf"):
            if href.startswith("/"):
                href = "https://www.icai.org" + href
            text = a.get_text(strip=True)
            results.append((href, text))

    return results


def get_pdf_date(url):
    try:
        r = requests.head(url, timeout=10)
        lm = r.headers.get("Last-Modified")
        if lm:
            return datetime.strptime(lm, "%a, %d %b %Y %H:%M:%S %Z")
    except:
        pass
    return None


def clean_title(anchor, url):
    if anchor and len(anchor) > 10:
        return anchor

    name = os.path.basename(url).replace(".pdf", "")
    return name.replace("_", " ").upper()


def build_embed(org, exam, title, url, date):
    if exam == "IMPORTANT":
        desc = f"{ORG_EMOJI[org]} **ICAI posted a new important announcement!** {EXAM_EMOJI['IMPORTANT']}"
    else:
        desc = f"{ORG_EMOJI[org]} **{org} posted a circular for {EXAM_EMOJI[exam]} {exam}!**"

    embed = {
        "title": title,
        "url": url,
        "description": desc,
        "color": 0x5865F2,
        "footer": {"text": f"Source: {org}"}
    }

    if date:
        embed["timestamp"] = date.isoformat()

    return embed


def send(embed):
    requests.post(WEBHOOK_URL, json={"embeds": [embed]})


def main():
    posted = load_state()

    for key, cfg in SOURCES.items():
        posted.setdefault(key, [])

        pdfs = fetch_pdfs(cfg["url"])
        items = []

        for url, anchor in pdfs:
            date = get_pdf_date(url)
            items.append((url, anchor, date))

        items.sort(key=lambda x: x[2] or datetime.min)

        for url, anchor, date in items:
            if url in posted[key]:
                continue

            if date and date < BASELINE_DATE:
                posted[key].append(url)
                continue

            title = clean_title(anchor, url)
            embed = build_embed(cfg["org"], cfg["exam"], title, url, date)
            send(embed)
            posted[key].append(url)

    save_state(posted)


if __name__ == "__main__":
    main()
