"""Summarize articles — supports Anthropic and Ollama (OpenAI-compatible)."""

from pathlib import Path

import yaml

WORDS_PER_MINUTE = 200
_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "config.yaml"


def _llm_config() -> dict:
    with open(_CONFIG_PATH) as f:
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
        return _summarize_ollama(system, user, model, base_url)
    else:
        return _summarize_anthropic(system, user, model)
