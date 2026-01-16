import requests
from bs4 import BeautifulSoup
import json
import os
from urllib.parse import urljoin
from datetime import datetime

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
if not DISCORD_WEBHOOK:
    raise RuntimeError("DISCORD_WEBHOOK not set")

STATE_FILE = "posted.json"

BASELINE_YEAR = 2026
BASELINE_MONTH = 1

SOURCES = {
    "JEE Main": {
        "url": "https://jeemain.nta.nic.in/Downloads/",
        "org": "NTA",
        "exam": "JEE MAIN",
        "emoji": "🧪"
    },
    "NEET": {
        "url": "https://neet.nta.nic.in/Downloads/",
        "org": "NTA",
        "exam": "NEET",
        "emoji": "🩺"
    },
    "ICAI BOS": {
        "url": "https://www.icai.org/category/bos-important-announcements/",
        "org": "ICAI",
        "exam": "IMPORTANT",
        "emoji": "🚨"
    },
    "ICAI Foundation": {
        "url": "https://www.icai.org/category/foundation-course/",
        "org": "ICAI",
        "exam": "CA FOUNDATION",
        "emoji": "📘"
    },
    "ICAI Intermediate": {
        "url": "https://www.icai.org/category/intermediate-course/",
        "org": "ICAI",
        "exam": "CA INTERMEDIATE",
        "emoji": "📗"
    },
    "ICAI Final": {
        "url": "https://www.icai.org/category/final-course/",
        "org": "ICAI",
        "exam": "CA FINAL",
        "emoji": "📕"
    }
}


def load_state():
    if not os.path.exists(STATE_FILE):
        return {"posted": {}, "baseline_done": False}

    with open(STATE_FILE) as f:
        data = json.load(f)

    if "posted" not in data:
        return {"posted": data, "baseline_done": False}

    return data


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def clean_title_from_url(url):
    name = url.split("/")[-1]
    return (
        name.replace("_", " ")
        .replace("-", " ")
        .replace(".pdf", "")
        .strip()
    )


def fetch_pdfs(source):
    r = requests.get(source["url"], timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")

    found = []

    for a in soup.select("a[href$='.pdf'], a[href*='/wp-content/uploads/']"):
        pdf_url = urljoin(source["url"], a["href"])
        title = a.get_text(strip=True)
        if not title or len(title) < 6:
            title = clean_title_from_url(pdf_url)

        date = None
        try:
            head = requests.head(pdf_url, timeout=10)
            lm = head.headers.get("Last-Modified")
            if lm:
                date = datetime.strptime(
                    lm, "%a, %d %b %Y %H:%M:%S %Z"
                )
        except:
            pass

        found.append((pdf_url, title, date))

    return found


def send_embed(src, title, url, date):
    if src["exam"] == "IMPORTANT":
        desc = f"{src['emoji']} **ICAI posted a new important announcement!**"
    else:
        desc = (
            f"{src['emoji']} **{src['org']} posted a circular for "
            f"{src['exam']}!**"
        )

    embed = {
        "title": title,
        "url": url,
        "description": desc,
        "color": 5793266
    }

    if date:
        embed["footer"] = {
            "text": f"Published: {date.strftime('%d-%m-%Y')}"
        }

    requests.post(DISCORD_WEBHOOK, json={"embeds": [embed]})


def main():
    state = load_state()

    for name, src in SOURCES.items():
        state["posted"].setdefault(name, [])

        pdfs = fetch_pdfs(src)
        pdfs.sort(key=lambda x: x[2] or datetime.min)

       BASELINE_LIMIT = 5  # per source
baseline_batch = pdfs[-BASELINE_LIMIT:]

for url, title, date in pdfs:
    if not state["baseline_done"]:
        if (url, title, date) not in baseline_batch:
            state["posted"][name].append(url)
            continue
    else:
        if url in state["posted"][name]:
            continue

    send_embed(src, title, url, date)
    state["posted"][name].append(url)


    state["baseline_done"] = True
    save_state(state)


if __name__ == "__main__":
    main()
