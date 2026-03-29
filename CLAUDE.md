# claudio-daily-report

A tool that fetches content from user-configured sources, processes it through an AI model, and produces a tailored daily digest readable in ~10 minutes.

## User Goal

Produce a daily personal digest across configurable topic categories. The user controls not just *which* categories exist, but also the *weight* of each — how much of the report's space and attention is devoted to each category on a given day.

## Current Categories

| Category | Description |
|---|---|
| Philosophy | General philosophy news, essays, and discussions |
| AI | Artificial intelligence news and research |
| Education | Early childhood education focused on children aged 2–3 years |

## Core Concepts

- **Category**: A named topic area with its own set of sources and a summarization persona/instructions
- **Weight**: A relative number per category (e.g., `2, 2, 1`). The report allocates reading time proportionally: a category with weight 2 in a 3-category setup gets 2/(2+2+1) = 40% of the total time budget.
- **Reading time**: Total target reading time for the report, configurable by the user (default: 10 minutes). Each category's time budget = `(weight / total_weight) * reading_time`.
- **Source**: A content origin assigned to a category. Initially RSS feeds provided by the user. Later: AI-suggested feeds, YouTube videos, podcasts, etc.
- **Daily Report**: The final output — an HTML file with a metadata header and category sections, sized to the configured reading time budget.

## Architecture (planned)

- `config/` — Categories, sources per category, weights, summarization instructions, output preferences
- `src/` — Core logic: source fetching, content parsing, AI summarization, report assembly
- `output/` — Generated reports as dated Markdown files

## Key Behaviors

- Fetch all sources for each category
- Compute each category's word/content budget from its weight and the total reading time (assume ~200 words/min average reading speed)
- Pass content to the Claude API with category-specific summarization instructions and an explicit word budget
- Avoid re-processing content already included in a previous report
- Output a single self-contained HTML file per day

## Report Structure (HTML)

```
┌─────────────────────────────────────────────────────────┐
│  Claudio Daily Report — March 29, 2026     [top-right]  │
│                          Philosophy: 40% · AI: 40% · .. │
├─────────────────────────────────────────────────────────┤
│  ## Philosophy                                          │
│  ...summaries...                                        │
│                                                         │
│  ## AI                                                  │
│  ...summaries...                                        │
│                                                         │
│  ## Education                                           │
│  ...summaries...                                        │
└─────────────────────────────────────────────────────────┘
```

- Metadata bar (top-right): shows each category name and its percentage of total reading time
- Each category section lists summarized items; length is proportional to the category's time budget
- Original article language is preserved — no translation

## Language Policy

Content is summarized in its original language. No translation is applied.

## Roadmap

### Phase 1 — RSS (current focus)
- User-provided RSS feeds per category
- Configurable weights
- Daily HTML report

### Phase 2 — AI-suggested sources
- Given a category description, ask Claude to suggest relevant RSS feeds
- User reviews and approves before they are added to config

### Phase 3 — Additional content types
- YouTube video summaries (via transcript)
- Podcast episode summaries (via transcript or description)
- Other content types as needed

## Development Notes

- Use the Claude API (Anthropic SDK) for summarization
- Config format: YAML (human-editable)
- Output: one self-contained `.html` file per run, saved to `output/YYYY-MM-DD.html`
- Reading speed assumption: 200 words/minute (used to compute word budgets from time weights)
- Track processed article/item IDs to avoid duplicates across runs
- Do not store full article content; only store report outputs and seen-item metadata
