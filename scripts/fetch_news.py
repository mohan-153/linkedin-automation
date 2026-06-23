"""
fetch_news.py
Pulls top tech stories from the Hacker News API (free, no key required).

API docs: https://github.com/HackerNews/API
"""
import os
import requests

HN_BASE = "https://hacker-news.firebaseio.com/v0"


def get_top_stories(limit=5):
    """
    Returns a list of dicts: [{title, url, score, hn_link}, ...]
    Picks from /topstories, skipping items with very low scores or missing titles.
    """
    limit = int(os.getenv("HN_STORY_LIMIT", limit))

    ids_resp = requests.get(f"{HN_BASE}/topstories.json", timeout=15)
    ids_resp.raise_for_status()
    story_ids = ids_resp.json()[:30]  # look at top 30, filter down to `limit`

    stories = []
    for sid in story_ids:
        if len(stories) >= limit:
            break
        item_resp = requests.get(f"{HN_BASE}/item/{sid}.json", timeout=15)
        if item_resp.status_code != 200:
            continue
        item = item_resp.json()
        if not item or item.get("type") != "story" or "title" not in item:
            continue
        stories.append(
            {
                "title": item.get("title"),
                "url": item.get("url", f"https://news.ycombinator.com/item?id={sid}"),
                "score": item.get("score", 0),
                "hn_link": f"https://news.ycombinator.com/item?id={sid}",
            }
        )
    return stories


def format_news_summary(stories):
    """Plain-text block to feed into the LLM prompt."""
    lines = []
    for i, s in enumerate(stories, 1):
        lines.append(f"{i}. {s['title']} (score: {s['score']}) - {s['url']}")
    return "\n".join(lines)


if __name__ == "__main__":
    stories = get_top_stories()
    print(format_news_summary(stories))
