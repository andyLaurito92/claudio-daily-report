"""Entry point: fetch → summarize → render → save."""

import json
import os
import sys
from datetime import date
from pathlib import Path

import yaml

# Load .env from repo root — works whether called directly or from server.py
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

from fetcher import fetch_category, load_seen_ids, save_seen_ids
from renderer import render_report
from store import save_articles, prune
from summarizer import summarize_category, word_budget


def load_config(path: str = "config/config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def main() -> None:
    config = load_config()

    reading_time = config.get("reading_time_minutes", 10)
    data_dir = config.get("data_dir", "data")
    output_dir = config.get("output", {}).get("dir", "output")
    categories_cfg = config.get("categories", [])

    total_weight = sum(c.get("weight", 1) for c in categories_cfg)

    # Load already-seen article IDs
    seen_ids = load_seen_ids(data_dir)
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

        # Persist raw articles for archive/search
        saved = save_articles(articles, name)
        if saved:
            print(f"          {saved} article(s) saved to archive")

        print(f"[claudio] Summarising '{name}' …")
        summary_md = summarize_category(name, description, articles, budget)

        # Track new IDs for this run
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

    # Save output
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{today.isoformat()}.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    # Save summary data so the server can re-render with latest UI
    json_path = os.path.join(output_dir, f"{today.isoformat()}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "date": today.isoformat(),
            "reading_time_minutes": reading_time,
            "summaries": summaries,
        }, f, ensure_ascii=False, indent=2)

    # Persist seen IDs
    save_seen_ids(data_dir, seen_ids | new_ids)

    print(f"\n[claudio] Report saved → {output_path}")


if __name__ == "__main__":
    # Run from repo root: python src/main.py
    sys.path.insert(0, os.path.dirname(__file__))
    main()
