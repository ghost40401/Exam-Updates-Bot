import requests
import json
import os
from bs4 import BeautifulSoup
from datetime import datetime

WEBHOOK = os.environ["DISCORD_WEBHOOK"]
STATE_FILE = "posted.json"

BASELINE_YEAR = 2026
BASELINE_MONTH = 1

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
    if not os.path.exists(STATE_FILE):
        return {"posted": {}, "baseline_done": False}

    with open(STATE_FILE) as f:
        data = json.load(f)

    # backward compatibility
    if "posted" not in data:
        return {
            "posted": data,
            "baseline_done": False
        }

    return data


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def fetch_posts(url):
    soup = BeautifulSoup(requests.get(url, timeout=20).text, "html.parser")
    posts = []

    for article in soup.select("article"):
        pdf = article.select_one("a[href$='.pdf']")
        if not pdf:
            continue

        title = pdf.get_text(strip=True)
        link = pdf["href"]
        if link.startswith("/"):
            link = "https://www.icai.org" + link

        date = None
        date_tag = article.select_one("time")
        if date_tag:
            try:
                date = datetime.strptime(date_tag.text.strip(), "%d %b %Y")
            except:
                pass

        posts.append((link, title, date))

    return posts


def send_embed(org, exam, title, url, date):
    if exam == "IMPORTANT":
        desc = "🚨 **ICAI posted a new important announcement!**"
    else:
        desc = f"🏛 **{org} posted a circular for {exam}!** {EMOJI[exam]}"

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

    requests.post(WEBHOOK, json={"embeds": [embed]})


def main():
    state = load_state()

    for key, cfg in SOURCES.items():
        state["posted"].setdefault(key, [])

        posts = fetch_posts(cfg["url"])
        posts.sort(key=lambda x: x[2] or datetime.min)

        for url, title, date in posts:
            is_jan_2026 = (
                date
                and date.year == BASELINE_YEAR
                and date.month == BASELINE_MONTH
            )

            if not state["baseline_done"]:
                if not is_jan_2026:
                    state["posted"][key].append(url)
                    continue
            else:
                if url in state["posted"][key]:
                    continue

            send_embed(cfg["org"], cfg["exam"], title, url, date)
            state["posted"][key].append(url)

    state["baseline_done"] = True
    save_state(state)


if __name__ == "__main__":
    main()
