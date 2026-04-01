"""Entry point: fetch → summarize → render → save."""

import json
import os
import sys
from datetime import date

import yaml

# Ensure paths are initialized before any other local imports
sys.path.insert(0, os.path.dirname(__file__))
from paths import CONFIG_FILE, DATA_DIR, OUTPUT_DIR, ENV_FILE, ensure_dirs  # noqa: E402

# Load .env from user data dir
try:
    from dotenv import load_dotenv
    load_dotenv(ENV_FILE)
except ImportError:
    pass

from fetcher import fetch_category, load_seen_ids, save_seen_ids  # noqa: E402
from renderer import render_report  # noqa: E402
from store import save_articles, prune  # noqa: E402
from summarizer import summarize_category, word_budget  # noqa: E402


def load_config() -> dict:
    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f)


def main() -> None:
    ensure_dirs()
    config = load_config()

    reading_time = config.get("reading_time_minutes", 10)
    categories_cfg = config.get("categories", [])
    total_weight = sum(c.get("weight", 1) for c in categories_cfg)

    # Load already-seen article IDs
    seen_ids = load_seen_ids(str(DATA_DIR))
    new_ids: set[str] = set()

    # Prune articles older than the rolling window
    window_days = config.get("archive", {}).get("window_days", 15)
    pruned = prune(window_days)
    if pruned:
        print(f"[claudio] Pruned {pruned} article(s) older than {window_days} days from archive")

    print(f"[claudio] Reading time: {reading_time}m | Categories: {len(categories_cfg)}")

    summaries: list[dict] = []

    for cat in categories_cfg:
        name = cat["name"]
        weight = cat.get("weight", 1)
        description = cat.get("description", name)
        pct = round(weight / total_weight * 100)
        budget = word_budget(weight, total_weight, reading_time)

        print(f"[claudio] Fetching '{name}' ({pct}%, ~{budget} words) …")
        articles = fetch_category(cat, seen_ids)
        print(f"          {len(articles)} new article(s) found")

        saved = save_articles(articles, name)
        if saved:
            print(f"          {saved} article(s) saved to archive")

        print(f"[claudio] Summarising '{name}' …")
        summary_md = summarize_category(name, description, articles, budget)

        for a in articles:
            new_ids.add(a["id"])

        summaries.append(
            {
                "name": name,
                "weight": weight,
                "pct": pct,
                "summary_md": summary_md,
                "article_links": [
                    {"title": a["title"], "link": a["link"]}
                    for a in articles if a.get("link")
                ],
            }
        )

    # Render HTML
    today = date.today()
    html = render_report(today, summaries, reading_time)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{today.isoformat()}.html"
    output_path.write_text(html, encoding="utf-8")

    json_path = OUTPUT_DIR / f"{today.isoformat()}.json"
    json_path.write_text(
        json.dumps({
            "date": today.isoformat(),
            "reading_time_minutes": reading_time,
            "summaries": summaries,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    save_seen_ids(str(DATA_DIR), seen_ids | new_ids)
    print(f"\n[claudio] Report saved → {output_path}")


if __name__ == "__main__":
    main()
