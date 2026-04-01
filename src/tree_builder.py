"""Build a 2-3 level semantic cluster tree for a category's archived articles.

Steps:
  1. Load articles from store (SQLite)
  2. Compute embeddings via Ollama (nomic-embed-text) — cached per article
  3. Hierarchical clustering (scipy) — cut at 2 levels
  4. Label each cluster with an evocative short phrase via LLM
  5. Write tree to tree_cache.json via store.save_tree()
"""

import math
from pathlib import Path

import yaml

import store
from paths import CONFIG_FILE

_EMBED_MODEL = "nomic-embed-text"
_MIN_ARTICLES_FOR_SPLIT = 3   # clusters smaller than this stay as leaves


def _llm_config() -> dict:
    with open(CONFIG_FILE) as f:
        cfg = yaml.safe_load(f)
    return cfg.get("llm", {"provider": "anthropic", "model": "claude-opus-4-6"})


# ── Embeddings ────────────────────────────────────────────────────────────────

def _embed_ollama(texts: list[str], base_url: str) -> list[list[float]]:
    import urllib.request
    import json
    base = base_url.rstrip("/")

    # Try new batch endpoint first (/api/embed, Ollama ≥ 0.5)
    try:
        url = base + "/api/embed"
        payload = json.dumps({"model": _EMBED_MODEL, "input": texts}).encode()
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        return data["embeddings"]
    except Exception:
        pass

    # Fall back to legacy single-prompt endpoint (/api/embeddings, Ollama < 0.5)
    results = []
    for text in texts:
        url = base + "/api/embeddings"
        payload = json.dumps({"model": _EMBED_MODEL, "prompt": text}).encode()
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        results.append(data["embedding"])
    return results


def _embed_anthropic(texts: list[str]) -> list[list[float]]:
    """Anthropic doesn't expose embeddings — fall back to Ollama on localhost."""
    return _embed_ollama(texts, "http://localhost:11434")


def _get_embeddings(articles: list[dict], cfg: dict) -> list[list[float]]:
    """Return embeddings for all articles, using cache where available."""
    provider = cfg.get("provider", "anthropic")
    base_url = cfg.get("ollama_base_url", "http://localhost:11434")

    embeddings: list[list[float] | None] = [None] * len(articles)
    missing_indices: list[int] = []

    for i, a in enumerate(articles):
        cached = store.get_embedding(a["id"])
        if cached is not None:
            embeddings[i] = cached
        else:
            missing_indices.append(i)

    if missing_indices:
        texts = [
            f"{articles[i]['title']}\n{articles[i].get('content', '')[:500]}"
            for i in missing_indices
        ]
        print(f"[tree_builder] Computing {len(texts)} embedding(s) …")
        if provider == "ollama":
            vecs = _embed_ollama(texts, base_url)
        else:
            vecs = _embed_anthropic(texts)

        for idx, vec in zip(missing_indices, vecs):
            store.save_embedding(articles[idx]["id"], vec)
            embeddings[idx] = vec

    return embeddings  # type: ignore[return-value]


# ── Clustering ────────────────────────────────────────────────────────────────

def _cluster(article_indices: list[int], embeddings: list[list[float]], n_clusters: int) -> list[list[int]]:
    """
    Split article_indices into n_clusters groups using agglomerative clustering.
    Falls back to equal split if scipy is unavailable.
    """
    if len(article_indices) <= n_clusters:
        return [[i] for i in article_indices]

    try:
        from scipy.cluster.hierarchy import linkage, fcluster
        import numpy as np

        vecs = np.array([embeddings[i] for i in article_indices], dtype=np.float32)
        # Normalise
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1
        vecs = vecs / norms

        Z = linkage(vecs, method="ward")
        labels = fcluster(Z, t=n_clusters, criterion="maxclust")

        clusters: dict[int, list[int]] = {}
        for pos, label in enumerate(labels):
            clusters.setdefault(label, []).append(article_indices[pos])
        return list(clusters.values())

    except ImportError:
        # scipy not available — fall back to simple equal split
        size = math.ceil(len(article_indices) / n_clusters)
        return [article_indices[i: i + size] for i in range(0, len(article_indices), size)]


# ── LLM labelling ─────────────────────────────────────────────────────────────

def _label_cluster(titles: list[str], cfg: dict) -> str:
    """Ask the LLM for a short evocative memory-trigger phrase for a cluster."""
    provider = cfg.get("provider", "anthropic")
    model = cfg.get("model", "claude-opus-4-6")

    titles_block = "\n".join(f"- {t}" for t in titles[:20])
    system = (
        "You are helping a reader navigate their reading history. "
        "Given a list of article titles, produce a single short phrase (4–8 words) "
        "that acts as a memory trigger — not a dry topic label, but something evocative "
        "that captures the feeling or theme of the group. "
        "Reply with ONLY the phrase, no punctuation at the end, no quotes."
    )
    user = f"Articles:\n{titles_block}\n\nMemory-trigger phrase:"

    if provider == "ollama":
        from openai import OpenAI
        base_url = cfg.get("ollama_base_url", "http://localhost:11434")
        client = OpenAI(base_url=base_url.rstrip("/") + "/v1", api_key="ollama")
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=32,
        )
        text = resp.choices[0].message.content or ""
        return text.strip().strip('"').strip("'")
    else:
        import anthropic
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model=model,
            max_tokens=32,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        block = msg.content[0]
        text = block.text if hasattr(block, "text") else ""
        return text.strip().strip('"').strip("'")


# ── Tree construction ─────────────────────────────────────────────────────────

def _build_subtree(
    article_indices: list[int],
    articles: list[dict],
    embeddings: list[list[float]],
    cfg: dict,
    depth: int,
    max_depth: int,
) -> dict:
    """Recursively build a tree node."""
    titles = [articles[i]["title"] for i in article_indices]
    label = _label_cluster(titles, cfg)

    if depth >= max_depth or len(article_indices) < _MIN_ARTICLES_FOR_SPLIT:
        # Leaf node — list article IDs
        return {
            "label": label,
            "articles": [
                {"id": articles[i]["id"], "title": articles[i]["title"], "link": articles[i]["link"]}
                for i in article_indices
            ],
        }

    # Determine number of child clusters (2–4 depending on size)
    n_children = min(4, max(2, len(article_indices) // 4))
    clusters = _cluster(article_indices, embeddings, n_children)

    # Drop singleton clusters back into a catch-all if needed
    children = []
    singles: list[int] = []
    for cluster in clusters:
        if len(cluster) < _MIN_ARTICLES_FOR_SPLIT and depth + 1 >= max_depth:
            singles.extend(cluster)
        else:
            children.append(
                _build_subtree(cluster, articles, embeddings, cfg, depth + 1, max_depth)
            )

    if singles:
        single_titles = [articles[i]["title"] for i in singles]
        single_label = _label_cluster(single_titles, cfg)
        children.append({
            "label": single_label,
            "articles": [
                {"id": articles[i]["id"], "title": articles[i]["title"], "link": articles[i]["link"]}
                for i in singles
            ],
        })

    return {"label": label, "children": children}


# ── Public entry point ────────────────────────────────────────────────────────

def build_tree(category: str, max_depth: int = 2) -> dict:
    """Build and cache the cluster tree for a category. Returns the tree dict."""
    articles = store.get_articles(category)
    if not articles:
        tree = {"label": category, "articles": []}
        store.save_tree(category, tree)
        return tree

    cfg = _llm_config()
    print(f"[tree_builder] Building tree for '{category}' ({len(articles)} articles) …")

    embeddings = _get_embeddings(articles, cfg)
    indices = list(range(len(articles)))
    tree = _build_subtree(indices, articles, embeddings, cfg, depth=1, max_depth=max_depth)
    # Override top-level label with the category name for clarity
    tree["label"] = category

    store.save_tree(category, tree)
    print(f"[tree_builder] Tree for '{category}' saved.")
    return tree
