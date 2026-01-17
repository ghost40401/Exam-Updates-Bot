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

BASELINE_START = datetime(2025, 10, 1)

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
    },
    "ICAI Main Announcements": {
    "url": "https://www.icai.org/category/announcements/",
    "org": "ICAI",
    "exam": "ANNOUNCEMENT",
    "emoji": "📢"
    }
}


def load_state():
    if not os.path.exists(STATE_FILE):
        return {"posted": {}, "baseline_done": {}}

    with open(STATE_FILE) as f:
        data = json.load(f)

    data.setdefault("posted", {})
    data.setdefault("baseline_done", {})

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

def extract_date_from_text(text):
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(text[-11:], fmt)
        except:
            pass
    return None

def fetch_pdfs(src):
    collected = []

    r = requests.get(src["url"], timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")

    def extract(section):
        if not section:
            return
        for a in section.select("a[href$='.pdf'], a[href*='/wp-content/uploads/']"):
            pdf_url = urljoin(src["url"], a["href"])
            title = a.get_text(" ", strip=True) or clean_title_from_url(pdf_url)

            # try to find date in nearby text
            text = a.parent.get_text(" ", strip=True)
            date = extract_date_from_text(text)

            collected.append((pdf_url, title, date))

    # -------- NTA --------
    if src["org"] == "NTA":
        if "jeemain" in src["url"]:
            extract(soup.find("div", id="1648447930282-deb48cc0-95ec"))
        if "neet" in src["url"]:
            extract(soup.find("div", id="1648449005032-46466f25-2ebe"))

        extract(soup.find("li", id="menu-item-6563"))

    # -------- ICAI --------
    if src["org"] == "ICAI":
        page = 1
        while True:
            url = src["url"] if page == 1 else src["url"].rstrip("/") + f"/page/{page}/"
            r = requests.get(url, timeout=20)
            if r.status_code != 200:
                break

            soup = BeautifulSoup(r.text, "html.parser")
            container = soup.select_one("div.container.mx-3")
            if not container:
                break

            found = False
            for a in container.select("a[href$='.pdf']"):
                found = True
                pdf_url = urljoin(url, a["href"])
                title = a.get_text(" ", strip=True) or clean_title_from_url(pdf_url)
                text = a.parent.get_text(" ", strip=True)
                date = extract_date_from_text(text)

                collected.append((pdf_url, title, date))

            if not found:
                break
            page += 1

    # de-duplicate
    seen = set()
    unique = []
    for u, t, d in collected:
        if u not in seen:
            seen.add(u)
            unique.append((u, t, d))

    return unique



def send_embed(src, title, url, date):
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
        "title": title,
        "url": url,
        "description": desc,
        "color": 5793266
    }

    if date:
        embed["footer"] = {
            "text": f"Published: {date.strftime('%d-%m-%Y')}"
        }

    requests.post(
        DISCORD_WEBHOOK,
        json={
            "content": "@everyone",
            "embeds": [embed]
        }
    )


def main():
    state = load_state()
    state["posted"].setdefault("_global", [])

    ALL_PDFS = []

    # 1️⃣ Collect everything first
    for name, src in SOURCES.items():
        pdfs = fetch_pdfs(src)
        for url, title, date in pdfs:
            if url in state["posted"]["_global"]:
                continue
            ALL_PDFS.append((url, title, date, src))

    # 2️⃣ Apply baseline rule
    BASELINE_START = datetime(2025, 10, 1)
    
    BASELINE_PDFS = []
    for url, title, date, src in ALL_PDFS:
        if date is None:
            BASELINE_PDFS.append((url, title, date, src))
        elif date >= BASELINE_START:
            BASELINE_PDFS.append((url, title, date, src))

    # 3️⃣ Global sort (oldest → newest, no-date first)
    BASELINE_PDFS.sort(
        key=lambda x: (x[2] is not None, x[2] or datetime.min)
    )

    # 4️⃣ Post in strict global order
    for url, title, date, src in BASELINE_PDFS:
        send_embed(src, title, url, date)
        state["posted"]["_global"].append(url)

    save_state(state)



if __name__ == "__main__":
    main()
