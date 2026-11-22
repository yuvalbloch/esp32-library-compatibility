"""The "What's new" list shown on the website (FARM/news.json, saved with the results).

Entries are written by the farm itself (update.py, report.py), never by hand:
    {"date": "2026-11-23", "kind": "core" | "release" | "broken" | "fixed", "text": "..."}
"""
import time

from common import FARM, load_json, save_json

NEWS_PATH = FARM / "news.json"
KEEP = 200


def load_news():
    try:
        return load_json(NEWS_PATH)
    except (OSError, ValueError):
        return []


def add_news(kind, text, date=None):
    news = load_news()
    news.insert(0, {"date": date or time.strftime("%Y-%m-%d"), "kind": kind, "text": text})
    save_json(NEWS_PATH, news[:KEEP])
