import requests
import json
import os
from bs4 import BeautifulSoup
from datetime import datetime

WEBHOOK = os.environ["DISCORD_WEBHOOK"]
STATE_FILE = "posted.json"

BASELINE_MONTH = (2026, 1)

SOURCES = {
    "ICAI Important": {
        "url": "https://www.icai.org/category/bos-important-announcements",
        "org": "ICAI",
        "exam": "IMPORTANT"
    },
    "ICAI Foundation": {
        "url": "https://www.icai.org/category/foundation-course",
        "org": "ICAI",
        "exam": "CA FOUNDATION"
    },
    "ICAI Intermediate": {
        "url": "https://www.icai.org/category/intermediate-course",
        "org": "ICAI",
        "exam": "CA INTERMEDIATE"
    },
    "ICAI Final": {
        "url": "https://www.icai.org/category/final-course",
        "org": "ICAI",
        "exam": "CA FINAL"
    }
}

EMOJI = {
    "IMPORTANT": "🚨",
    "CA FOUNDATION": "📘",
    "CA INTERMEDIATE": "📗",
    "CA FINAL": "📕"
}


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"posted": {}, "baseline_done": False}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def fetch_posts(url):
    soup = BeautifulSoup(requests.get(url, timeout=20).text, "html.parser")
    posts = []

    for post in soup.select("article"):
        link = post.select_one("a[href$='.pdf']")
        if not link:
            continue

        title = link.get_text(strip=True)
        href = link["href"]
        if href.startswith("/"):
            href = "https://www.icai.org" + href

        date_tag = post.select_one("time")
        date = None
        if date_tag:
            date = datetime.strptime(date_tag.text.strip(), "%d %b %Y")

        posts.append((href, title, date))

    return posts


def send(org, exam, title, url, date):
    if exam == "IMPORTANT":
        desc = f"🚨 **ICAI posted a new important announcement!**"
    else:
        desc = f"🏛 **ICAI posted a circular for {exam}!** {EMOJI[exam]}"

    embed = {
        "title": title,
        "url": url,
        "description": desc,
        "color": 0x5865F2
    }

    if date:
        embed["footer"] = {"text": f"Published: {date.strftime('%d-%m-%Y')}"}

    requests.post(WEBHOOK, json={"embeds": [embed]})


def main():
    state = load_state()

    for key, cfg in SOURCES.items():
        state["posted"].setdefault(key, [])

        posts = fetch_posts(cfg["url"])
        posts.sort(key=lambda x: x[2] or datetime.min)

        for url, title, date in posts:
            is_jan_2026 = date and (date.year, date.month) == BASELINE_MONTH

            if not state["baseline_done"]:
                if not is_jan_2026:
                    state["posted"][key].append(url)
                    continue
            else:
                if url in state["posted"][key]:
                    continue

            send(cfg["org"], cfg["exam"], title, url, date)
            state["posted"][key].append(url)

    state["baseline_done"] = True
    save_state(state)


if __name__ == "__main__":
    main()
