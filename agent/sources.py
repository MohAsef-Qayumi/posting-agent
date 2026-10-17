"""Fresh headlines from RSS feeds, used as inspiration for news-driven pillars."""
import feedparser


def fetch_headlines(feeds: list[str], limit: int = 15) -> list[str]:
    headlines: list[str] = []
    for url in feeds:
        try:
            parsed = feedparser.parse(url)
        except Exception as e:  # a broken feed must never stop the daily post
            print(f"[sources] skipped {url}: {e}")
            continue
        for entry in parsed.entries[:6]:
            title = (entry.get("title") or "").strip()
            if title:
                headlines.append(f"- {title} ({entry.get('link', '')})")
    return headlines[:limit]
