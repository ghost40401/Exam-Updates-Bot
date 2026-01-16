import requests
import json
import os
from bs4 import BeautifulSoup
from datetime import datetime
from PyPDF2 import PdfReader
from io import BytesIO

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


def fetch_pdfs(source):
    r = requests.get(source)
    soup = BeautifulSoup(r.text, "html.parser")

    pdfs = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith(".pdf"):
            if href.startswith("/"):
                href = "https://www.icai.org" + href
            pdfs.append((href, a.get_text(strip=True)))

    return pdfs


def get_pdf_date(url):
    try:
        head = requests.head(url, timeout=10)
        lm = head.headers.get("Last-Modified")
        if lm:
            return datetime.strptime(lm, "%a, %d %b %Y %H:%M:%S %Z")
    except:
        pass
    return None


def get_pdf_title(url, anchor_text):
    try:
        r = requests.get(url, timeout=15)
        reader = PdfReader(BytesIO(r.content))
        meta = reader.metadata
        if meta and meta.title and len(meta.title.strip()) > 5:
            return meta.title.strip()
    except:
        pass

    if anchor_text and len(anchor_text) > 8:
        return anchor_text

    return os.path.basename(url).replace(".pdf", "")


def build_embed(org, exam, title, url, date):
    if exam == "IMPORTANT":
        description = f"{ORG_EMOJI[org]} **ICAI posted a new important announcement!** {EXAM_EMOJI['IMPORTANT']}"
    else:
        description = (
            f"{ORG_EMOJI[org]} **{org} posted a circular for "
            f"{EXAM_EMOJI[exam]} {exam}!**"
        )

    embed = {
        "title": title,
        "url": url,
        "description": description,
        "color": 0x5865F2,
        "footer": {"text": f"Source: {org}"},
    }

    if date:
        embed["timestamp"] = date.isoformat()

    return embed


def send(embed):
    requests.post(WEBHOOK_URL, json={"embeds": [embed]})


def main():
    posted = load_state()

    for name, data in SOURCES.items():
        posted.setdefault(name, [])
        pdfs = fetch_pdfs(data["url"])

        dated = []
        for url, anchor in pdfs:
            date = get_pdf_date(url)
            dated.append((url, anchor, date))

        dated.sort(key=lambda x: x[2] or datetime.min)

        for url, anchor, date in dated:
            if url in posted[name]:
                continue

            if date and date < BASELINE_DATE:
                posted[name].append(url)
                continue

            title = get_pdf_title(url, anchor)
            embed = build_embed(data["org"], data["exam"], title, url, date)
            send(embed)
            posted[name].append(url)

    save_state(posted)


if __name__ == "__main__":
    main()
