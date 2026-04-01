"""Summarize articles — supports Anthropic and Ollama (OpenAI-compatible)."""

import re
from pathlib import Path

import yaml

from paths import CONFIG_FILE  # noqa: E402

WORDS_PER_MINUTE = 200


def _llm_config() -> dict:
    with open(CONFIG_FILE) as f:
        cfg = yaml.safe_load(f)
    return cfg.get("llm", {"provider": "anthropic", "model": "claude-opus-4-6"})


def word_budget(weight: int, total_weight: int, reading_time_minutes: int) -> int:
    """Return the target word count for one category."""
    return int((weight / total_weight) * reading_time_minutes * WORDS_PER_MINUTE)


def _build_prompt(name: str, description: str, articles: list[dict], budget: int) -> tuple[str, str]:
    articles_block = ""
    for i, a in enumerate(articles[:25], 1):
        content_preview = a["content"][:1200] if a["content"] else "(no content)"
        articles_block += (
            f"\n--- Article {i} ---\n"
            f"Title: {a['title']}\n"
            f"URL: {a['link']}\n"
            f"Content: {content_preview}\n"
        )

    system = (
        "You are a concise news curator producing a personal daily digest. "
        "Select the most interesting and relevant articles and summarize them clearly. "
        "Do NOT translate — always write each summary in the same language as the original article. "
        "Format your output in Markdown."
    )
    user = (
        f"Category: **{name}**\n"
        f"Category description: {description}\n"
        f"Target length: approximately {budget} words total across all summaries.\n\n"
        f"Articles:\n{articles_block}\n\n"
        "For each article you choose to include, use this format:\n"
        "### [Article Title](URL)\n"
        "2–3 sentence summary.\n\n"
        "Skip articles that are not relevant to the category description. "
        "Stay within the word budget."
    )
    return system, user


def _summarize_anthropic(system: str, user: str, model: str) -> str:
    import anthropic
    client = anthropic.Anthropic()
    with client.messages.stream(
        model=model,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        return stream.get_final_message().content[0].text


def _summarize_ollama(system: str, user: str, model: str, base_url: str) -> str:
    from openai import OpenAI
    client = OpenAI(base_url=base_url.rstrip("/") + "/v1", api_key="ollama")
    stream = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        stream=True,
    )
    result = ""
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            result += delta
    return result


def _inject_links(summary_md: str, articles: list[dict]) -> str:
    """Ensure every ### heading has a link, matching against source articles by title."""
    # Build a lookup: normalised title -> URL
    def _norm(s: str) -> str:
        return re.sub(r"\W+", " ", s).strip().lower()

    lookup: dict[str, str] = {}
    for a in articles:
        if a.get("link") and a.get("title"):
            lookup[_norm(a["title"])] = a["link"]

    def _best_url(heading: str) -> str | None:
        h = _norm(heading)
        # Exact match
        if h in lookup:
            return lookup[h]
        # Substring match: article title is contained in heading or vice-versa
        for norm_title, url in lookup.items():
            if norm_title and (norm_title in h or h in norm_title):
                return url
        # Token overlap: ≥60% of article title tokens appear in heading
        h_tokens = set(h.split())
        for norm_title, url in lookup.items():
            t_tokens = set(norm_title.split())
            if t_tokens and len(t_tokens & h_tokens) / len(t_tokens) >= 0.6:
                return url
        return None

    # Matches a bare URL in parentheses at the end of a heading, e.g. "(example.com/path)"
    _bare_url_re = re.compile(
        r'\s*\(((?:https?://)?[A-Za-z0-9][-A-Za-z0-9.]+\.[A-Za-z]{2,}[^)]*)\)$'
    )

    def _replace(m: re.Match) -> str:
        title = m.group(1).strip()
        # Already a proper markdown link — leave it
        if title.startswith("["):
            return m.group(0)
        # Title has a bare URL in parens — strip it and use that URL
        suffix = _bare_url_re.search(title)
        if suffix:
            clean = title[:suffix.start()].strip()
            url = suffix.group(1)
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            return f"### [{clean}]({url})"
        # No URL in title — match against original articles
        url = _best_url(title)
        if url:
            return f"### [{title}]({url})"
        return m.group(0)

    return re.sub(r"^### (.+)$", _replace, summary_md, flags=re.MULTILINE)


def summarize_category(
    name: str,
    description: str,
    articles: list[dict],
    budget: int,
) -> str:
    """Return a Markdown summary for one category using the configured LLM."""
    if not articles:
        return f"*No new articles found for {name} today.*"

    cfg = _llm_config()
    provider = cfg.get("provider", "anthropic")
    model = cfg.get("model", "claude-opus-4-6")
    system, user = _build_prompt(name, description, articles, budget)

    if provider == "ollama":
        base_url = cfg.get("ollama_base_url", "http://localhost:11434")
        result = _summarize_ollama(system, user, model, base_url)
    else:
        result = _summarize_anthropic(system, user, model)

    return _inject_links(result, articles)
