"""Render the daily report as a self-contained HTML file."""

import re
import markdown as md
from datetime import date

_PALETTE = ["#4a6fa5", "#5e8a5e", "#8b5e6b", "#7a6e4b", "#5e7a8b"]


def _wrap_articles(html: str) -> str:
    """Wrap each h3 + following p(s) in a clickable .article card.

    URLs are stored in data-href on the card — not shown in the title.
    A small ↗ button at bottom-right lets users inspect/copy the source URL.
    """
    # Step 1: convert legacy "Title (bare-url)" pattern to a proper <a> link
    def _linkify_h3(m: re.Match) -> str:
        url = m.group(2)
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        return f'<h3><a href="{url}">{m.group(1).strip()}</a></h3>'

    html = re.sub(
        r"<h3>([^<]+?)\s*\(((?:https?://)?[A-Za-z0-9][-A-Za-z0-9.]+\.[A-Za-z]{2,}[^)]*)\)</h3>",
        _linkify_h3,
        html,
    )

    # Strip <h4> tags that LLMs sometimes insert between <h3> and <p> (e.g. duplicate URL lines)
    html = re.sub(r'<h4>[^<]*</h4>', '', html)

    # Step 2: wrap h3 + p(s) in .article
    wrapped = re.sub(
        r"(<h3>.*?</h3>)((?:\s*<p>.*?</p>)+)",
        lambda m: f'<div class="article">{m.group(1)}{m.group(2)}</div>',
        html,
        flags=re.DOTALL,
    )

    # Step 3: for each card, extract the URL, strip the <a> from h3, add data-href + icon btn
    def _clean_title(t: str) -> str:
        """Strip any bare URL or (URL: ...) suffix from a display title."""
        t = re.sub(r'\s*\(URL:\s*https?://[^)]+\)', '', t)
        t = re.sub(
            r'\s*\((?:https?://)?[A-Za-z0-9][-A-Za-z0-9.]+\.[A-Za-z]{2,}[^)]*\)', '', t
        )
        return t.strip()

    def _process_card(m: re.Match) -> str:
        inner = m.group(1)
        link_m = re.search(
            r'<h3><a href="(https?://[^"]+)"[^>]*>(.*?)</a></h3>', inner, re.DOTALL
        )
        if link_m:
            url, title = link_m.group(1), _clean_title(link_m.group(2))
            inner = inner[: link_m.start()] + f"<h3>{title}</h3>" + inner[link_m.end() :]
            btn = '<button class="article-link-btn" title="View source URL">&#8599;</button>'
            return f'<div class="article" data-href="{url}">{inner}{btn}</div>'
        return f'<div class="article">{inner}</div>'

    return re.sub(
        r'<div class="article">(.*?)</div>', _process_card, wrapped, flags=re.DOTALL
    )


# ── CSS ───────────────────────────────────────────────────────────────────────
# Written with real braces — inserted via str.replace, not .format()
_CSS = """\
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  [hidden] { display: none !important; }
  html { font-size: 16px; }
  body {
    font-family: Georgia, 'Times New Roman', serif;
    background: #f7f6f2;
    color: #1c1c1e;
    line-height: 1.7;
    min-height: 100vh;
  }
  .page {
    max-width: 1400px;
    margin: 0 auto;
    padding: 0 1.5rem 1.5rem;
    display: flex;
    flex-direction: column;
    height: 100vh;
    overflow: hidden;
  }

  /* ── Loading bar ── */
  #progress-bar {
    position: fixed;
    top: 0; left: 0;
    height: 3px; width: 0%;
    background: #4a6fa5;
    transition: width 0.25s ease;
    z-index: 999;
    display: none;
  }

  /* ── Error banner ── */
  #error-banner {
    background: #fff5f5;
    border: 1px solid #fca5a5;
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin-bottom: 1.5rem;
    color: #b91c1c;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 0.85rem;
    align-items: flex-start;
    gap: 0.75rem;
    display: none;
  }
  #error-banner.visible { display: flex; }
  .error-body { flex: 1; }
  .error-title { font-weight: 600; margin-bottom: 0.2rem; }
  .error-msg { opacity: 0.9; word-break: break-word; font-size: 0.82rem; }
  .error-close {
    flex-shrink: 0;
    background: none; border: none;
    cursor: pointer; color: #b91c1c;
    font-size: 1.1rem; padding: 0 0.15rem;
    line-height: 1; opacity: 0.6;
  }
  .error-close:hover { opacity: 1; }

  /* ── Header ── */
  header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding: 1.5rem 0 1rem;
    border-bottom: 2px solid #1c1c1e;
    margin-bottom: 1.25rem;
    gap: 1.5rem;
    flex-shrink: 0;
  }
  .report-title {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 1.75rem;
    font-weight: 800;
    letter-spacing: -0.04em;
    line-height: 1;
    color: #1c1c1e;
  }
  .report-meta {
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 0.82rem;
    color: #6b6b6b;
    margin-top: 0.45rem;
  }
  .header-right {
    text-align: right;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.55rem;
  }
  .badges { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 0.25rem; }
  .badge {
    display: inline-block;
    padding: 0.2rem 0.65rem;
    border-radius: 999px;
    color: #fff;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 0.73rem;
    font-weight: 500;
    letter-spacing: 0.01em;
  }

  /* ── Update button ── */
  #update-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.38rem 0.95rem;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 0.8rem;
    font-weight: 500;
    color: #3a3a3c;
    background: #fff;
    border: 1.5px solid #d1d1d6;
    border-radius: 999px;
    cursor: pointer;
    transition: border-color 0.15s, color 0.15s, box-shadow 0.15s;
    white-space: nowrap;
  }
  #update-btn:hover:not(:disabled) {
    border-color: #3a3a3c;
    box-shadow: 0 1px 5px rgba(0,0,0,0.1);
  }
  #update-btn:disabled { opacity: 0.5; cursor: default; }
  #update-btn.loading { border-color: #4a6fa5; color: #4a6fa5; }
  .btn-icon { font-size: 0.95rem; line-height: 1; display: inline-block; }
  .btn-icon.spin { animation: spin 0.9s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* ── Category grid (side-by-side columns) ── */
  .categories-grid {
    flex: 1;
    display: flex;
    gap: 1.1rem;
    min-height: 0;
    padding-bottom: 1rem;
  }

  /* ── Category sections ── */
  .category-section {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }
  .category-section .content {
    flex: 1;
    overflow-y: auto;
    padding-right: 0.3rem;
    scrollbar-width: thin;
    scrollbar-color: #d1d1d6 transparent;
  }
  .category-section .content::-webkit-scrollbar { width: 4px; }
  .category-section .content::-webkit-scrollbar-track { background: transparent; }
  .category-section .content::-webkit-scrollbar-thumb { background: #d1d1d6; border-radius: 4px; }
  .category-heading {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #3a3a3c;
    padding-bottom: 0.65rem;
    margin-bottom: 1.25rem;
    border-bottom-width: 2px;
    border-bottom-style: solid;
  }
  .category-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .category-pct {
    font-size: 0.7rem;
    color: #8a8a8e;
    font-weight: 400;
    margin-left: auto;
    text-transform: none;
    letter-spacing: 0.01em;
  }

  /* ── Article cards ── */
  .article {
    position: relative;
    padding: 1.1rem 1.35rem 2rem;
    background: #fff;
    border-radius: 10px;
    margin-bottom: 0.8rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
    transition: box-shadow 0.2s ease;
  }
  .article:hover { box-shadow: 0 4px 14px rgba(0,0,0,0.09); }
  .article h3 {
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 0.97rem;
    font-weight: 600;
    line-height: 1.4;
    margin-bottom: 0.4rem;
    color: #1c1c1e;
  }
  .article p {
    font-size: 0.93rem;
    color: #4a4a4e;
    line-height: 1.65;
  }
  .article em { color: #8a8a8e; }

  /* ── Article link button + tooltip ── */
  .article-link-btn {
    position: absolute;
    bottom: 0.55rem; right: 0.7rem;
    width: 22px; height: 22px;
    display: inline-flex; align-items: center; justify-content: center;
    background: none;
    border: 1.5px solid #d1d1d6;
    border-radius: 50%;
    cursor: pointer;
    color: #aeaeb2;
    font-size: 0.72rem;
    line-height: 1;
    transition: border-color 0.12s, color 0.12s, background 0.12s;
    z-index: 1;
  }
  .article-link-btn:hover { border-color: #4a6fa5; color: #4a6fa5; background: #f0f4fb; }
  .link-tooltip {
    position: absolute;
    bottom: 2rem; right: 0;
    background: #1c1c1e;
    color: #e5e5ea;
    border-radius: 8px;
    padding: 0.45rem 0.75rem;
    font-size: 0.72rem;
    font-family: 'SF Mono', 'Fira Code', monospace;
    white-space: normal;
    word-break: break-all;
    max-width: min(400px, 90vw);
    z-index: 50;
    box-shadow: 0 4px 14px rgba(0,0,0,0.25);
    pointer-events: auto;
  }
  .link-tooltip a { color: #7ab8f5; text-decoration: none; }
  .link-tooltip a:hover { text-decoration: underline; }

  /* ── Empty state ── */
  .empty-state {
    text-align: center;
    padding: 5rem 0 3rem;
    color: #8a8a8e;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  }
  .empty-state h2 {
    font-size: 1.15rem;
    font-weight: 600;
    color: #3a3a3c;
    margin-bottom: 0.5rem;
  }
  .empty-state p { font-size: 0.9rem; line-height: 1.6; }
  .empty-state .hint {
    margin-top: 1.5rem;
    font-size: 0.82rem;
    color: #aeaeb2;
  }

  /* ── Footer ── */
  footer {
    margin-top: 3rem;
    padding-top: 1rem;
    border-top: 1px solid #e5e5ea;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 0.74rem;
    color: #aeaeb2;
    text-align: center;
  }

  /* ── Model settings ── */
  .controls { display: flex; align-items: center; gap: 0.45rem; }
  .settings-wrap { position: relative; }
  #settings-btn {
    display: inline-flex; align-items: center; justify-content: center;
    width: 32px; height: 32px;
    background: #fff;
    border: 1.5px solid #d1d1d6;
    border-radius: 50%;
    cursor: pointer;
    color: #6b6b6b;
    font-size: 0.95rem;
    transition: border-color 0.15s, color 0.15s;
  }
  #settings-btn:hover { border-color: #3a3a3c; color: #1c1c1e; }
  #settings-btn.active { border-color: #4a6fa5; color: #4a6fa5; background: #f0f4fb; }
  .popover {
    position: absolute;
    right: 0; top: calc(100% + 8px);
    background: #fff;
    border: 1px solid #e5e5ea;
    border-radius: 12px;
    box-shadow: 0 8px 28px rgba(0,0,0,0.13), 0 2px 6px rgba(0,0,0,0.06);
    padding: 1.1rem 1.15rem;
    width: 220px;
    z-index: 200;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  }
  .popover-title {
    font-size: 0.72rem; font-weight: 700;
    letter-spacing: 0.08em; text-transform: uppercase;
    color: #8a8a8e; margin-bottom: 0.9rem;
  }
  .pop-field { margin-bottom: 0.8rem; }
  .pop-label {
    display: block; font-size: 0.75rem; font-weight: 600;
    color: #3a3a3c; margin-bottom: 0.35rem;
  }
  .radio-row { display: flex; gap: 0.8rem; }
  .radio-opt {
    display: flex; align-items: center; gap: 0.3rem;
    font-size: 0.82rem; color: #3a3a3c; cursor: pointer;
  }
  .model-select {
    width: 100%;
    padding: 0.32rem 0.5rem;
    border: 1.5px solid #d1d1d6; border-radius: 6px;
    font-size: 0.82rem; color: #1c1c1e; background: #fff;
    cursor: pointer;
  }
  .model-select:focus { border-color: #4a6fa5; outline: none; }
  .model-select:disabled { opacity: 0.5; }
  .pop-hint { font-size: 0.72rem; color: #aeaeb2; margin-top: 0.25rem; }
  .save-btn {
    width: 100%; padding: 0.42rem;
    background: #1c1c1e; color: #fff;
    border: none; border-radius: 7px;
    font-size: 0.8rem; font-weight: 600;
    cursor: pointer; margin-top: 0.2rem;
    transition: opacity 0.15s, background 0.2s;
  }
  .save-btn:hover:not(:disabled) { opacity: 0.82; }
  .save-btn:disabled { opacity: 0.45; cursor: default; }
  .save-btn.saved { background: #5e8a5e; }
  .pop-setup-link {
    display: block; text-align: center; margin-top: 0.65rem;
    font-size: 0.75rem; color: #4a6fa5; cursor: pointer; text-decoration: none;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  }
  .pop-setup-link:hover { text-decoration: underline; }

  /* ── Setup modal ── */
  .setup-modal {
    background: #fff; border-radius: 14px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.2);
    width: 100%; max-width: 560px; max-height: 88vh;
    display: flex; flex-direction: column;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  }
  .setup-tabs {
    display: flex; border-bottom: 1px solid #e5e5ea; flex-shrink: 0; padding: 0 1.4rem;
  }
  .setup-tab {
    padding: 0.75rem 1rem; font-size: 0.85rem; font-weight: 600;
    color: #8a8a8e; border: none; background: none; cursor: pointer;
    border-bottom: 2.5px solid transparent; margin-bottom: -1px;
    transition: color 0.12s, border-color 0.12s;
  }
  .setup-tab.active { color: #4a6fa5; border-bottom-color: #4a6fa5; }
  .setup-panel { display: none; flex: 1; overflow-y: auto; padding: 1.2rem 1.4rem; }
  .setup-panel.active { display: block; }
  .setup-step {
    display: flex; gap: 0.85rem; margin-bottom: 1.1rem; align-items: flex-start;
  }
  .setup-step-num {
    flex-shrink: 0; width: 24px; height: 24px; border-radius: 50%;
    background: #4a6fa5; color: #fff; font-size: 0.75rem; font-weight: 700;
    display: flex; align-items: center; justify-content: center;
  }
  .setup-step-body { flex: 1; }
  .setup-step-title { font-size: 0.88rem; font-weight: 600; color: #1c1c1e; margin-bottom: 0.2rem; }
  .setup-step-desc { font-size: 0.8rem; color: #6b6b6b; line-height: 1.5; }
  .setup-step-desc a { color: #4a6fa5; }
  .setup-input-row { display: flex; gap: 0.5rem; margin-top: 0.5rem; }
  .setup-input {
    flex: 1; padding: 0.4rem 0.7rem;
    border: 1.5px solid #d1d1d6; border-radius: 7px;
    font-size: 0.82rem; color: #1c1c1e; outline: none;
    font-family: 'SF Mono', 'Fira Code', monospace;
  }
  .setup-input:focus { border-color: #4a6fa5; }
  .setup-test-btn {
    padding: 0.4rem 0.9rem; background: #4a6fa5; color: #fff;
    border: none; border-radius: 7px; font-size: 0.82rem; font-weight: 600;
    cursor: pointer; white-space: nowrap; transition: opacity 0.12s;
  }
  .setup-test-btn:hover { opacity: 0.85; }
  .setup-test-btn:disabled { opacity: 0.5; cursor: default; }
  .setup-status {
    margin-top: 0.5rem; font-size: 0.8rem; padding: 0.4rem 0.7rem;
    border-radius: 7px; display: none;
  }
  .setup-status.ok { display: block; background: #f0faf0; color: #2d6a2d; }
  .setup-status.err { display: block; background: #fff5f5; color: #b91c1c; }
  .setup-code {
    display: inline-flex; align-items: center; gap: 0.5rem;
    background: #f0f0f5; border-radius: 6px; padding: 0.3rem 0.65rem;
    font-family: 'SF Mono', 'Fira Code', monospace; font-size: 0.78rem;
    color: #1c1c1e; margin-top: 0.35rem;
  }
  .setup-copy-btn {
    background: none; border: none; cursor: pointer; color: #8a8a8e;
    font-size: 0.75rem; padding: 0; transition: color 0.12s;
  }
  .setup-copy-btn:hover { color: #1c1c1e; }
  .setup-divider {
    border: none; border-top: 1px solid #f0f0f5; margin: 0.5rem 0 1rem;
  }

  /* ── Article cards — full card clickable ── */
  .article { cursor: pointer; }

  /* ── Manage button ── */
  #manage-btn {
    display: inline-flex; align-items: center; gap: 0.4rem;
    padding: 0.38rem 0.95rem;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 0.8rem; font-weight: 500;
    color: #3a3a3c; background: #fff;
    border: 1.5px solid #d1d1d6; border-radius: 999px;
    cursor: pointer; white-space: nowrap;
    transition: border-color 0.15s, box-shadow 0.15s;
  }
  #manage-btn:hover { border-color: #3a3a3c; box-shadow: 0 1px 5px rgba(0,0,0,0.1); }

  /* ── Manage modal overlay ── */
  .modal-overlay {
    position: fixed; inset: 0;
    background: rgba(0,0,0,0.45);
    z-index: 500;
    display: flex; align-items: center; justify-content: center;
    padding: 1rem;
  }
  .manage-modal {
    background: #fff; border-radius: 14px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.2);
    width: 100%; max-width: 580px; max-height: 85vh;
    display: flex; flex-direction: column;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  }
  .modal-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 1.2rem 1.4rem 1rem;
    border-bottom: 1px solid #e5e5ea; flex-shrink: 0;
  }
  .modal-title { font-size: 1rem; font-weight: 700; color: #1c1c1e; }
  .modal-close {
    background: none; border: none; cursor: pointer;
    color: #8a8a8e; font-size: 1.2rem; line-height: 1;
    padding: 0.2rem; transition: color 0.12s;
  }
  .modal-close:hover { color: #1c1c1e; }
  .modal-body { overflow-y: auto; padding: 1rem 1.4rem; flex: 1; }

  /* ── Category list view ── */
  .cat-color-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
  .cat-list-row {
    display: flex; align-items: center; gap: 0.7rem;
    padding: 0.8rem 1rem; border: 1.5px solid #e5e5ea; border-radius: 10px;
    margin-bottom: 0.55rem; cursor: pointer;
    transition: border-color 0.12s, background 0.12s;
  }
  .cat-list-row:hover { border-color: #4a6fa5; background: #f8f9ff; }
  .cat-list-name { font-weight: 600; font-size: 0.9rem; color: #1c1c1e; flex: 1; }
  .cat-list-meta { display: flex; gap: 0.4rem; align-items: center; }
  .cat-list-badge {
    font-size: 0.72rem; color: #6b6b6b; background: #e5e5ea;
    padding: 0.15rem 0.5rem; border-radius: 999px; white-space: nowrap;
  }
  .cat-list-badge.zero { background: #fff0f0; color: #b91c1c; }
  .cat-list-chevron { color: #aeaeb2; font-size: 0.8rem; }

  /* ── Category detail view ── */
  .cat-detail-back {
    display: inline-flex; align-items: center; gap: 0.35rem;
    background: none; border: none; cursor: pointer; color: #4a6fa5;
    font-size: 0.82rem; font-weight: 500; padding: 0 0 0.75rem 0;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  }
  .cat-detail-back:hover { text-decoration: underline; }
  .cat-detail-header {
    display: flex; align-items: center; gap: 0.6rem;
    padding-bottom: 0.75rem; border-bottom: 1px solid #f0f0f5; margin-bottom: 0.85rem;
  }
  .cat-detail-name { font-weight: 700; font-size: 1rem; color: #1c1c1e; flex: 1; }
  .cat-detail-badges { display: flex; gap: 0.4rem; }
  .cat-detail-badge {
    font-size: 0.72rem; color: #6b6b6b; background: #e5e5ea;
    padding: 0.15rem 0.5rem; border-radius: 999px;
  }
  .cat-detail-actions { display: flex; gap: 0.3rem; }
  .cat-action-btn {
    background: none; border: none; cursor: pointer; color: #8a8a8e;
    font-size: 0.85rem; padding: 0.25rem 0.4rem; border-radius: 5px;
    transition: background 0.12s, color 0.12s;
  }
  .cat-action-btn:hover { background: #f0f0f5; color: #1c1c1e; }
  .cat-action-btn.delete:hover { background: #fff5f5; color: #b91c1c; }
  .cat-desc { font-size: 0.82rem; color: #6b6b6b; margin-bottom: 0.85rem; }
  .cat-sources-label {
    font-size: 0.7rem; font-weight: 700; color: #6b6b6b;
    text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0.4rem;
  }
  .source-list { margin: 0; padding: 0; list-style: none; }
  .source-item {
    display: flex; align-items: center; gap: 0.5rem; padding: 0.3rem 0;
    font-size: 0.78rem; color: #3a3a3c; border-bottom: 1px solid #f5f5f7;
  }
  .source-item:last-child { border-bottom: none; }
  .source-url {
    flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    font-family: 'SF Mono', 'Fira Code', monospace; font-size: 0.75rem; color: #4a4a4e;
  }
  .source-remove-btn {
    flex-shrink: 0; background: none; border: none; cursor: pointer;
    color: #aeaeb2; font-size: 0.85rem; padding: 0.1rem 0.3rem;
    border-radius: 4px; transition: color 0.12s, background 0.12s;
  }
  .source-remove-btn:hover { color: #b91c1c; background: #fff5f5; }
  .add-source-row { display: flex; gap: 0.5rem; margin-top: 0.65rem; align-items: center; }
  .add-source-input {
    flex: 1; padding: 0.3rem 0.6rem;
    border: 1.5px solid #d1d1d6; border-radius: 6px;
    font-size: 0.78rem; color: #1c1c1e; outline: none;
  }
  .add-source-input:focus { border-color: #4a6fa5; }
  .add-source-btn {
    padding: 0.3rem 0.7rem; background: #1c1c1e; color: #fff;
    border: none; border-radius: 6px; font-size: 0.78rem; font-weight: 600;
    cursor: pointer; white-space: nowrap; transition: opacity 0.12s;
  }
  .add-source-btn:hover { opacity: 0.8; }

  /* ── Discover sources ── */
  .discover-section { margin-top: 1.1rem; }
  .discover-toggle-btn {
    display: inline-flex; align-items: center; gap: 0.4rem;
    background: none; border: 1.5px solid #d1d1d6; border-radius: 8px;
    padding: 0.38rem 0.85rem; font-size: 0.82rem; font-weight: 500; color: #3a3a3c;
    cursor: pointer; transition: border-color 0.15s, color 0.15s;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  }
  .discover-toggle-btn:hover { border-color: #4a6fa5; color: #4a6fa5; }
  .discover-panel {
    margin-top: 0.65rem; padding: 0.85rem 1rem;
    border: 1.5px solid #d1d1d6; border-radius: 10px; background: #fafafa;
  }
  .discover-hint {
    font-size: 0.78rem; color: #6b6b6b; margin-bottom: 0.55rem; line-height: 1.5;
  }
  .discover-input-row { display: flex; gap: 0.5rem; }
  .discover-input {
    flex: 1; padding: 0.4rem 0.7rem;
    border: 1.5px solid #d1d1d6; border-radius: 7px;
    font-size: 0.82rem; color: #1c1c1e; outline: none;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  }
  .discover-input:focus { border-color: #4a6fa5; }
  .discover-find-btn {
    padding: 0.4rem 0.9rem; background: #4a6fa5; color: #fff;
    border: none; border-radius: 7px; font-size: 0.82rem; font-weight: 600;
    cursor: pointer; white-space: nowrap; transition: opacity 0.12s;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  }
  .discover-find-btn:hover { opacity: 0.85; }
  .discover-find-btn:disabled { opacity: 0.5; cursor: default; }
  .discover-results { margin-top: 0.75rem; }
  .discover-result-item {
    display: flex; align-items: center; gap: 0.6rem;
    padding: 0.45rem 0; border-bottom: 1px solid #f0f0f5;
  }
  .discover-result-item:last-child { border-bottom: none; }
  .discover-result-check { flex-shrink: 0; accent-color: #4a6fa5; width: 15px; height: 15px; cursor: pointer; }
  .discover-result-info { flex: 1; min-width: 0; }
  .discover-result-title { font-size: 0.82rem; font-weight: 600; color: #1c1c1e; }
  .discover-result-url {
    font-size: 0.72rem; color: #8a8a8e; white-space: nowrap;
    overflow: hidden; text-overflow: ellipsis;
    font-family: 'SF Mono', 'Fira Code', monospace;
  }
  .discover-add-btn {
    margin-top: 0.65rem; padding: 0.38rem 0.9rem; background: #1c1c1e; color: #fff;
    border: none; border-radius: 7px; font-size: 0.8rem; font-weight: 600;
    cursor: pointer; transition: opacity 0.12s;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  }
  .discover-add-btn:hover { opacity: 0.8; }

  /* ── Edit / add category forms ── */
  .edit-form { padding: 0.75rem 1rem; background: #f8f8fa; }
  .edit-row { display: flex; gap: 0.75rem; margin-bottom: 0.55rem; }
  .edit-field { flex: 1; }
  .edit-field.weight-field { flex: 0 0 90px; }
  .edit-label {
    display: block; font-size: 0.7rem; font-weight: 600; color: #6b6b6b;
    text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0.25rem;
  }
  .edit-input {
    width: 100%; padding: 0.35rem 0.6rem;
    border: 1.5px solid #d1d1d6; border-radius: 6px;
    font-size: 0.82rem; color: #1c1c1e; outline: none; background: #fff;
  }
  .edit-input:focus { border-color: #4a6fa5; }
  .edit-actions { display: flex; gap: 0.5rem; justify-content: flex-end; margin-top: 0.4rem; }
  .edit-save-btn {
    padding: 0.35rem 0.85rem; background: #1c1c1e; color: #fff;
    border: none; border-radius: 6px; font-size: 0.8rem; font-weight: 600;
    cursor: pointer; transition: opacity 0.12s;
  }
  .edit-save-btn:hover { opacity: 0.8; }
  .edit-cancel-btn {
    padding: 0.35rem 0.75rem; background: none; color: #6b6b6b;
    border: 1.5px solid #d1d1d6; border-radius: 6px;
    font-size: 0.8rem; cursor: pointer; transition: border-color 0.12s;
  }
  .edit-cancel-btn:hover { border-color: #6b6b6b; }

  /* ── Add category ── */
  .add-cat-section { margin-top: 0.5rem; }
  .add-cat-btn {
    width: 100%; padding: 0.6rem; background: none;
    border: 2px dashed #d1d1d6; border-radius: 10px;
    color: #6b6b6b; font-size: 0.85rem; font-weight: 500; cursor: pointer;
    transition: border-color 0.15s, color 0.15s;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  }
  .add-cat-btn:hover { border-color: #4a6fa5; color: #4a6fa5; }
  .add-cat-form {
    border: 1.5px solid #4a6fa5; border-radius: 10px;
    padding: 0.85rem 1rem; background: #f0f4fb;
  }
  .add-cat-form-title {
    font-size: 0.78rem; font-weight: 700; color: #4a6fa5;
    text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0.7rem;
  }

  /* ── Archive button ── */
  #archive-btn {
    display: inline-flex; align-items: center; gap: 0.4rem;
    padding: 0.38rem 0.95rem;
    background: #fff; border: 1.5px solid #d1d1d6; border-radius: 8px;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 0.82rem; font-weight: 500; color: #3a3a3c; cursor: pointer;
    transition: border-color 0.15s, box-shadow 0.15s;
  }
  #archive-btn:hover { border-color: #3a3a3c; box-shadow: 0 1px 5px rgba(0,0,0,0.1); }

  /* ── Archive modal ── */
  .archive-modal {
    background: #fff; border-radius: 14px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.2);
    width: 100%; max-width: 680px; max-height: 85vh;
    display: flex; flex-direction: column;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  }
  .archive-tabs {
    display: flex; gap: 0; border-bottom: 1px solid #e5e5ea; flex-shrink: 0;
    padding: 0 1.4rem;
  }
  .archive-tab {
    padding: 0.75rem 1rem; font-size: 0.85rem; font-weight: 600;
    color: #8a8a8e; border: none; background: none; cursor: pointer;
    border-bottom: 2.5px solid transparent; margin-bottom: -1px;
    transition: color 0.12s, border-color 0.12s;
  }
  .archive-tab.active { color: #4a6fa5; border-bottom-color: #4a6fa5; }
  .archive-tab-panel { display: none; flex: 1; overflow-y: auto; padding: 1rem 1.4rem; }
  .archive-tab-panel.active { display: block; }

  /* Explore tab */
  .arc-cat-list { list-style: none; padding: 0; margin: 0; }
  .arc-cat-item {
    display: flex; align-items: center; justify-content: space-between;
    padding: 0.7rem 0.9rem; border: 1.5px solid #e5e5ea; border-radius: 10px;
    margin-bottom: 0.55rem; cursor: pointer;
    transition: border-color 0.12s, background 0.12s;
  }
  .arc-cat-item:hover { border-color: #4a6fa5; background: #f8f9ff; }
  .arc-cat-name { font-size: 0.9rem; font-weight: 600; color: #1c1c1e; }
  .arc-cat-count { font-size: 0.75rem; color: #8a8a8e; }
  .arc-breadcrumb {
    display: flex; align-items: center; gap: 0.4rem;
    font-size: 0.78rem; color: #8a8a8e; margin-bottom: 0.75rem; flex-wrap: wrap;
  }
  .arc-breadcrumb-item { cursor: pointer; color: #4a6fa5; }
  .arc-breadcrumb-item:hover { text-decoration: underline; }
  .arc-breadcrumb-sep { color: #d1d1d6; }
  .arc-node-list { list-style: none; padding: 0; margin: 0; }
  .arc-node-item {
    padding: 0.65rem 0.9rem; border: 1.5px solid #e5e5ea; border-radius: 10px;
    margin-bottom: 0.5rem; cursor: pointer;
    transition: border-color 0.12s, background 0.12s;
  }
  .arc-node-item:hover { border-color: #4a6fa5; background: #f8f9ff; }
  .arc-node-label { font-size: 0.88rem; font-weight: 600; color: #1c1c1e; }
  .arc-node-count { font-size: 0.73rem; color: #8a8a8e; margin-top: 0.15rem; }
  .arc-article-item {
    display: flex; align-items: flex-start; gap: 0.6rem;
    padding: 0.6rem 0.9rem; border: 1.5px solid #e5e5ea; border-radius: 10px;
    margin-bottom: 0.5rem; text-decoration: none;
    transition: border-color 0.12s, background 0.12s;
  }
  .arc-article-item:hover { border-color: #4a6fa5; background: #f8f9ff; }
  .arc-article-title { font-size: 0.85rem; color: #1c1c1e; flex: 1; line-height: 1.4; }
  .arc-article-ext { font-size: 0.9rem; color: #8a8a8e; flex-shrink: 0; }
  .arc-loading {
    text-align: center; padding: 2.5rem 0; color: #8a8a8e; font-size: 0.85rem;
  }
  .arc-empty { text-align: center; padding: 2rem 0; color: #aeaeb2; font-size: 0.85rem; }

  /* Search tab */
  .arc-search-row {
    display: flex; gap: 0.5rem; margin-bottom: 1rem;
  }
  .arc-search-input {
    flex: 1; padding: 0.5rem 0.8rem;
    border: 1.5px solid #d1d1d6; border-radius: 8px;
    font-size: 0.88rem; color: #1c1c1e; outline: none;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  }
  .arc-search-input:focus { border-color: #4a6fa5; }
  .arc-search-btn {
    padding: 0.5rem 1rem; background: #1c1c1e; color: #fff;
    border: none; border-radius: 8px; font-size: 0.85rem; font-weight: 600;
    cursor: pointer; transition: opacity 0.12s; white-space: nowrap;
  }
  .arc-search-btn:hover { opacity: 0.8; }
  .arc-result-item {
    padding: 0.65rem 0.9rem; border: 1.5px solid #e5e5ea; border-radius: 10px;
    margin-bottom: 0.5rem;
  }
  .arc-result-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 0.5rem; }
  .arc-result-title {
    font-size: 0.88rem; font-weight: 600; color: #1c1c1e; flex: 1; line-height: 1.4;
  }
  .arc-result-link {
    font-size: 0.78rem; color: #4a6fa5; text-decoration: none; white-space: nowrap; flex-shrink: 0;
  }
  .arc-result-link:hover { text-decoration: underline; }
  .arc-result-meta { display: flex; gap: 0.6rem; margin-top: 0.3rem; }
  .arc-result-cat {
    font-size: 0.7rem; color: #fff; padding: 0.1rem 0.5rem;
    border-radius: 999px; background: #4a6fa5;
  }
  .arc-result-date { font-size: 0.7rem; color: #8a8a8e; }"""


# ── JavaScript ────────────────────────────────────────────────────────────────
# Written with real braces — inserted via str.replace, not .format()
_JS = """\
  let _progress = 0, _progressTimer = null;

  function _startProgress() {
    const bar = document.getElementById('progress-bar');
    bar.style.display = 'block';
    _progress = 0;
    _progressTimer = setInterval(() => {
      _progress += (90 - _progress) * 0.055;
      bar.style.width = _progress + '%';
    }, 250);
  }

  function _endProgress() {
    clearInterval(_progressTimer);
    const bar = document.getElementById('progress-bar');
    bar.style.width = '100%';
    setTimeout(() => { bar.style.display = 'none'; bar.style.width = '0'; }, 400);
  }

  function showError(msg) {
    document.getElementById('error-msg').textContent = msg;
    document.getElementById('error-banner').classList.add('visible');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function dismissError() {
    document.getElementById('error-banner').classList.remove('visible');
  }

  function _resetBtn(label) {
    const btn = document.getElementById('update-btn');
    btn.disabled = false;
    btn.classList.remove('loading');
    document.getElementById('btn-icon').classList.remove('spin');
    document.getElementById('btn-label').textContent = label;
  }

  function triggerUpdate() {
    const btn = document.getElementById('update-btn');
    btn.disabled = true;
    btn.classList.add('loading');
    document.getElementById('btn-icon').classList.add('spin');
    document.getElementById('btn-label').textContent = 'Updating\u2026';
    dismissError();
    _startProgress();

    fetch('/update', { method: 'POST' })
      .then(r => r.json())
      .then(() => poll())
      .catch(() => {
        _endProgress();
        _resetBtn('Update Feed');
        showError('Could not reach the server. Is claudio running?');
      });
  }

  function poll() {
    setTimeout(() => {
      fetch('/status')
        .then(r => r.json())
        .then(data => {
          if (data.running) {
            poll();
          } else if (data.error) {
            _endProgress();
            _resetBtn('Update Feed');
            showError('Update failed \u2014 ' + data.error);
          } else {
            _endProgress();
            window.location.reload();
          }
        })
        .catch(() => poll());
    }, 3000);
  }

  // ── Model settings ──────────────────────────────────────────────────────────
  let _allModels = { anthropic: [], ollama: [] };

  function toggleSettings() {
    const pop = document.getElementById('settings-popover');
    const btn = document.getElementById('settings-btn');
    const opening = pop.hidden;
    pop.hidden = !opening;
    btn.classList.toggle('active', opening);
    if (opening) loadSettings();
  }

  document.addEventListener('click', e => {
    const wrap = document.querySelector('.settings-wrap');
    if (wrap && !wrap.contains(e.target)) {
      const pop = document.getElementById('settings-popover');
      if (pop) { pop.hidden = true; }
      const btn = document.getElementById('settings-btn');
      if (btn) btn.classList.remove('active');
    }
  });

  async function loadSettings() {
    const select = document.getElementById('model-select');
    select.disabled = true;
    select.innerHTML = '<option>Loading\u2026</option>';
    try {
      const [cfg, models] = await Promise.all([
        fetch('/api/config').then(r => r.json()),
        fetch('/api/models').then(r => r.json()),
      ]);
      _allModels = models;
      const radio = document.querySelector('input[name="provider"][value="' + cfg.provider + '"]');
      if (radio) radio.checked = true;
      _fillModels(cfg.provider, cfg.model);
    } catch(e) {
      select.innerHTML = '<option>Error loading</option>';
      select.disabled = false;
    }
  }

  function _fillModels(provider, current) {
    const select = document.getElementById('model-select');
    const list = _allModels[provider] || [];
    select.disabled = false;
    if (list.length === 0) {
      select.innerHTML = provider === 'ollama'
        ? '<option value="">Ollama not running</option>'
        : '<option value="">No models found</option>';
    } else {
      select.innerHTML = list.map(m =>
        '<option value="' + m + '"' + (m === current ? ' selected' : '') + '>' + m + '</option>'
      ).join('');
    }
  }

  function onProviderChange() {
    const p = document.querySelector('input[name="provider"]:checked');
    if (p) _fillModels(p.value, null);
  }

  async function saveSettings() {
    const p = document.querySelector('input[name="provider"]:checked');
    const model = document.getElementById('model-select').value;
    if (!p || !model) return;
    const btn = document.getElementById('save-settings-btn');
    btn.disabled = true;
    btn.textContent = 'Saving\u2026';
    try {
      await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: p.value, model }),
      });
      btn.textContent = 'Saved \u2713';
      btn.classList.add('saved');
      setTimeout(() => {
        btn.textContent = 'Save';
        btn.classList.remove('saved');
        btn.disabled = false;
        document.getElementById('settings-popover').hidden = true;
        document.getElementById('settings-btn').classList.remove('active');
      }, 1200);
    } catch(e) {
      btn.textContent = 'Error';
      btn.disabled = false;
      setTimeout(() => { btn.textContent = 'Save'; }, 1500);
    }
  }

  // ── Article cards: click to open, ↗ button to show URL tooltip ─────────────
  document.querySelectorAll('.article').forEach(function(card) {
    card.addEventListener('click', function(e) {
      if (e.target.closest('.article-link-btn')) return;
      if (e.target.closest('.link-tooltip')) return;
      if (e.target.closest('a')) return;
      var url = card.dataset.href;
      if (url) window.open(url, '_blank', 'noopener,noreferrer');
    });
  });

  document.addEventListener('click', function(e) {
    var btn = e.target.closest('.article-link-btn');
    if (btn) {
      e.stopPropagation();
      var card = btn.closest('.article');
      var existing = card.querySelector('.link-tooltip');
      document.querySelectorAll('.link-tooltip').forEach(function(t) { t.remove(); });
      if (existing) return;
      var url = card.dataset.href;
      if (!url) return;
      var tt = document.createElement('div');
      tt.className = 'link-tooltip';
      tt.innerHTML = '<a href="' + url + '" target="_blank" rel="noopener noreferrer">' + url + '</a>';
      card.appendChild(tt);
      return;
    }
    if (!e.target.closest('.link-tooltip')) {
      document.querySelectorAll('.link-tooltip').forEach(function(t) { t.remove(); });
    }
  });

  // ── Manage categories modal ──────────────────────────────────────────────────
  const _MGR_PALETTE = ['#4a6fa5','#5e8a5e','#8b5e6b','#7a6e4b','#5e7a8b'];
  var _mgrCats = [];

  function openManage() {
    document.getElementById('manage-overlay').hidden = false;
    _loadMgrCats();
  }

  function closeManage() {
    document.getElementById('manage-overlay').hidden = true;
  }

  document.addEventListener('click', function(e) {
    const ov = document.getElementById('manage-overlay');
    if (ov && e.target === ov) closeManage();
  });

  async function _loadMgrCats() {
    const body = document.getElementById('manage-body');
    body.innerHTML = '<div style="text-align:center;padding:2rem;color:#8a8a8e">Loading\u2026</div>';
    try {
      _mgrCats = await fetch('/api/categories').then(r => r.json());
      _renderMgr();
    } catch(e) {
      body.innerHTML = '<div style="color:#b91c1c;padding:1rem">Failed to load categories.</div>';
    }
  }

  function _esc(s) {
    if (!s) return '';
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  // ── List view ────────────────────────────────────────────────────────────────
  function _renderMgr() {
    const body = document.getElementById('manage-body');
    const total = _mgrCats.reduce(function(s,c){ return s + (c.weight||1); }, 0);
    var html = '';
    _mgrCats.forEach(function(cat, i) {
      const pct = total > 0 ? Math.round((cat.weight||1) / total * 100) : 0;
      const color = _MGR_PALETTE[i % _MGR_PALETTE.length];
      const srcCount = (cat.sources || []).length;
      const zeroClass = srcCount === 0 ? ' zero' : '';
      html += '<div class="cat-list-row" data-idx="'+i+'">'
        + '<span class="cat-color-dot" style="background:'+color+'"></span>'
        + '<span class="cat-list-name">'+_esc(cat.name)+'</span>'
        + '<span class="cat-list-meta">'
        + '<span class="cat-list-badge">'+pct+'%</span>'
        + '<span class="cat-list-badge'+zeroClass+'">'+srcCount+' feed'+(srcCount===1?'':'s')+'</span>'
        + '</span>'
        + '<span class="cat-list-chevron">&#8250;</span>'
        + '</div>';
    });
    html += '<div class="add-cat-section" id="add-cat-section">'
      + '<button class="add-cat-btn" id="add-cat-btn">+ Add Category</button>'
      + '</div>';
    body.innerHTML = html;

    body.querySelectorAll('.cat-list-row').forEach(function(row) {
      row.addEventListener('click', function() {
        _mgrShowDetail(parseInt(row.dataset.idx, 10));
      });
    });
    document.getElementById('add-cat-btn').addEventListener('click', _mgrShowAddForm);
  }

  // ── Detail view ──────────────────────────────────────────────────────────────
  function _mgrShowDetail(idx) {
    const cat = _mgrCats[idx];
    const total = _mgrCats.reduce(function(s,c){ return s + (c.weight||1); }, 0);
    const pct = total > 0 ? Math.round((cat.weight||1) / total * 100) : 0;
    const color = _MGR_PALETTE[idx % _MGR_PALETTE.length];
    const sources = cat.sources || [];
    const body = document.getElementById('manage-body');

    var html = '<button class="cat-detail-back" id="det-back">&#8592; All categories</button>'
      + '<div class="cat-detail-header">'
      + '<span class="cat-color-dot" style="background:'+color+'"></span>'
      + '<span class="cat-detail-name">'+_esc(cat.name)+'</span>'
      + '<span class="cat-detail-badges">'
      + '<span class="cat-detail-badge">'+pct+'%</span>'
      + '<span class="cat-detail-badge">w'+_esc(cat.weight)+'</span>'
      + '</span>'
      + '<div class="cat-detail-actions">'
      + '<button class="cat-action-btn" id="det-edit" title="Edit">&#9998;</button>'
      + '<button class="cat-action-btn delete" id="det-del" title="Delete">&#215;</button>'
      + '</div>'
      + '</div>';

    if (cat.description) html += '<div class="cat-desc">'+_esc(cat.description)+'</div>';

    html += '<div class="cat-sources-label">Sources ('+sources.length+')</div>'
      + '<ul class="source-list" id="det-source-list">';
    sources.forEach(function(src, si) {
      html += '<li class="source-item">'
        + '<span class="source-url" title="'+_esc(src.url)+'">'+_esc(src.url)+'</span>'
        + '<button class="source-remove-btn" data-si="'+si+'" title="Remove">&#x2715;</button>'
        + '</li>';
    });
    html += '</ul>'
      + '<div class="add-source-row">'
      + '<input class="add-source-input" id="det-src-in" type="url" placeholder="https://example.com/feed.rss">'
      + '<button class="add-source-btn" id="det-src-add">Add RSS</button>'
      + '</div>'
      + '<div class="discover-section">'
      + '<button class="discover-toggle-btn" id="det-discover-btn">&#128269; Discover sources</button>'
      + '<div id="det-discover-panel" hidden>'
      + '<div class="discover-panel">'
      + '<div class="discover-hint">Describe what you want to read, or paste a website you already visit:</div>'
      + '<div class="discover-input-row">'
      + '<input class="discover-input" id="det-discover-in" placeholder="e.g. Formula 1 news, or https://marca.com">'
      + '<button class="discover-find-btn" id="det-discover-find">Find sources</button>'
      + '</div>'
      + '<div id="det-discover-results"></div>'
      + '</div>'
      + '</div>'
      + '</div>';

    body.innerHTML = html;

    document.getElementById('det-back').addEventListener('click', _loadMgrCats);
    document.getElementById('det-edit').addEventListener('click', function() { _mgrEditCat(idx); });
    document.getElementById('det-del').addEventListener('click', function() { _mgrDeleteCat(idx); });
    document.getElementById('det-src-add').addEventListener('click', function() { _mgrAddSrc(idx); });
    document.getElementById('det-src-in').addEventListener('keydown', function(e) {
      if (e.key === 'Enter') _mgrAddSrc(idx);
    });
    document.getElementById('det-source-list').querySelectorAll('.source-remove-btn').forEach(function(btn) {
      btn.addEventListener('click', function() { _mgrRemoveSrc(idx, parseInt(btn.dataset.si, 10)); });
    });
    document.getElementById('det-discover-btn').addEventListener('click', function() {
      const panel = document.getElementById('det-discover-panel');
      panel.hidden = !panel.hidden;
      if (!panel.hidden) document.getElementById('det-discover-in').focus();
    });
    document.getElementById('det-discover-find').addEventListener('click', function() { _mgrDiscover(idx); });
    document.getElementById('det-discover-in').addEventListener('keydown', function(e) {
      if (e.key === 'Enter') _mgrDiscover(idx);
    });
  }

  // ── Edit / delete / sources ───────────────────────────────────────────────────
  function _mgrEditCat(idx) {
    const cat = _mgrCats[idx];
    const body = document.getElementById('manage-body');
    body.innerHTML = '<button class="cat-detail-back" id="edit-back">&#8592; Back</button>'
      + '<div class="edit-form" style="margin-top:0.5rem">'
      + '<div class="edit-row">'
      + '<div class="edit-field"><label class="edit-label">Name</label>'
      + '<input class="edit-input" id="ed-name" value="'+_esc(cat.name)+'"></div>'
      + '<div class="edit-field weight-field"><label class="edit-label">Weight</label>'
      + '<input class="edit-input" id="ed-wt" type="number" min="1" value="'+_esc(cat.weight)+'"></div>'
      + '</div>'
      + '<div class="edit-row">'
      + '<div class="edit-field"><label class="edit-label">Description</label>'
      + '<input class="edit-input" id="ed-desc" value="'+_esc(cat.description||'')+'"></div>'
      + '</div>'
      + '<div class="edit-actions">'
      + '<button class="edit-cancel-btn" id="ed-cancel">Cancel</button>'
      + '<button class="edit-save-btn" id="ed-save">Save</button>'
      + '</div></div>';
    document.getElementById('edit-back').addEventListener('click', function() { _mgrShowDetail(idx); });
    document.getElementById('ed-cancel').addEventListener('click', function() { _mgrShowDetail(idx); });
    document.getElementById('ed-save').addEventListener('click', function() { _mgrSaveCat(idx); });
    document.getElementById('ed-name').focus();
  }

  async function _mgrSaveCat(idx) {
    const name = document.getElementById('ed-name').value.trim();
    const weight = parseInt(document.getElementById('ed-wt').value) || 1;
    const description = document.getElementById('ed-desc').value.trim();
    if (!name) { document.getElementById('ed-name').focus(); return; }
    try {
      await fetch('/api/categories/'+idx, {
        method: 'PUT', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({name, weight, description}),
      });
      await _loadMgrCats();
    } catch(e) { showError('Failed to save category.'); }
  }

  async function _mgrDeleteCat(idx) {
    const cat = _mgrCats[idx];
    if (!confirm('Delete "'+cat.name+'"? This cannot be undone.')) return;
    try {
      await fetch('/api/categories/'+idx, {method:'DELETE'});
      await _loadMgrCats();
    } catch(e) { showError('Failed to delete category.'); }
  }

  async function _mgrAddSrc(idx) {
    const input = document.getElementById('det-src-in');
    const url = (input ? input.value : '').trim();
    if (!url) { if (input) input.focus(); return; }
    try {
      await fetch('/api/categories/'+idx+'/sources', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({url, type:'rss'}),
      });
      _mgrCats = await fetch('/api/categories').then(r => r.json());
      _mgrShowDetail(idx);
    } catch(e) { showError('Failed to add source.'); }
  }

  async function _mgrRemoveSrc(idx, srcIdx) {
    try {
      await fetch('/api/categories/'+idx+'/sources/'+srcIdx, {method:'DELETE'});
      _mgrCats = await fetch('/api/categories').then(r => r.json());
      _mgrShowDetail(idx);
    } catch(e) { showError('Failed to remove source.'); }
  }

  // ── Discover sources ──────────────────────────────────────────────────────────
  async function _mgrDiscover(idx) {
    const input = document.getElementById('det-discover-in');
    const q = input.value.trim();
    if (!q) { input.focus(); return; }
    const btn = document.getElementById('det-discover-find');
    const resultsEl = document.getElementById('det-discover-results');
    btn.disabled = true;
    btn.textContent = 'Searching\u2026';
    resultsEl.innerHTML = '';
    try {
      const res = await fetch('/api/categories/'+idx+'/discover', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({query: q}),
      });
      const feeds = await res.json();
      btn.disabled = false;
      btn.textContent = 'Find sources';
      if (feeds.error) { resultsEl.innerHTML = '<div style="color:#b91c1c;font-size:0.8rem;margin-top:0.5rem">'+_esc(feeds.error)+'</div>'; return; }
      if (!feeds.length) { resultsEl.innerHTML = '<div style="color:#8a8a8e;font-size:0.8rem;margin-top:0.5rem">No feeds found. Try a different description or URL.</div>'; return; }
      var html = '<div class="discover-results" id="disc-list">';
      feeds.forEach(function(f, fi) {
        html += '<div class="discover-result-item">'
          + '<input type="checkbox" class="discover-result-check" id="disc-cb-'+fi+'" data-url="'+_esc(f.url)+'" checked>'
          + '<label class="discover-result-info" for="disc-cb-'+fi+'">'
          + '<div class="discover-result-title">'+_esc(f.title)+'</div>'
          + '<div class="discover-result-url">'+_esc(f.url)+'</div>'
          + '</label></div>';
      });
      html += '</div><button class="discover-add-btn" id="disc-add-btn">Add selected</button>';
      resultsEl.innerHTML = html;
      document.getElementById('disc-add-btn').addEventListener('click', function() { _mgrAddDiscovered(idx); });
    } catch(e) {
      btn.disabled = false;
      btn.textContent = 'Find sources';
      resultsEl.innerHTML = '<div style="color:#b91c1c;font-size:0.8rem;margin-top:0.5rem">Search failed.</div>';
    }
  }

  async function _mgrAddDiscovered(idx) {
    const checked = document.querySelectorAll('#disc-list .discover-result-check:checked');
    const urls = Array.from(checked).map(function(cb) { return cb.dataset.url; });
    if (!urls.length) return;
    try {
      for (const url of urls) {
        await fetch('/api/categories/'+idx+'/sources', {
          method: 'POST', headers: {'Content-Type':'application/json'},
          body: JSON.stringify({url, type:'rss'}),
        });
      }
      _mgrCats = await fetch('/api/categories').then(r => r.json());
      _mgrShowDetail(idx);
    } catch(e) { showError('Failed to add sources.'); }
  }

  // ── Add new category form ─────────────────────────────────────────────────────
  function _mgrShowAddForm() {
    document.getElementById('add-cat-section').innerHTML = '<div class="add-cat-form">'
      + '<div class="add-cat-form-title">New Category</div>'
      + '<div class="edit-row">'
      + '<div class="edit-field"><label class="edit-label">Name</label>'
      + '<input class="edit-input" id="nc-name" placeholder="e.g. Science"></div>'
      + '<div class="edit-field weight-field"><label class="edit-label">Weight</label>'
      + '<input class="edit-input" id="nc-wt" type="number" min="1" value="1"></div>'
      + '</div>'
      + '<div class="edit-row">'
      + '<div class="edit-field"><label class="edit-label">Description (optional)</label>'
      + '<input class="edit-input" id="nc-desc" placeholder="Topic focus\u2026"></div>'
      + '</div>'
      + '<div class="edit-actions">'
      + '<button class="edit-cancel-btn" id="nc-cancel">Cancel</button>'
      + '<button class="edit-save-btn" id="nc-save">Add</button>'
      + '</div></div>';
    document.getElementById('nc-name').focus();
    document.getElementById('nc-cancel').addEventListener('click', _renderMgr);
    document.getElementById('nc-save').addEventListener('click', _mgrSaveNew);
  }

  async function _mgrSaveNew() {
    const name = document.getElementById('nc-name').value.trim();
    const weight = parseInt(document.getElementById('nc-wt').value) || 1;
    const description = document.getElementById('nc-desc').value.trim();
    if (!name) { document.getElementById('nc-name').focus(); return; }
    try {
      await fetch('/api/categories', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({name, weight, description}),
      });
      await _loadMgrCats();
    } catch(e) { showError('Failed to add category.'); }
  }

  // ── Setup guide modal ────────────────────────────────────────────────────
  function openSetup() {
    document.getElementById('settings-popover').hidden = true;
    document.getElementById('settings-btn').classList.remove('active');
    document.getElementById('setup-overlay').hidden = false;
  }

  function closeSetup() {
    document.getElementById('setup-overlay').hidden = true;
  }

  document.addEventListener('click', function(e) {
    const ov = document.getElementById('setup-overlay');
    if (ov && e.target === ov) closeSetup();
  });

  function switchSetupTab(name) {
    document.getElementById('setup-tab-anthropic').classList.toggle('active', name === 'anthropic');
    document.getElementById('setup-tab-ollama').classList.toggle('active', name === 'ollama');
    document.getElementById('setup-panel-anthropic').classList.toggle('active', name === 'anthropic');
    document.getElementById('setup-panel-ollama').classList.toggle('active', name === 'ollama');
  }

  async function setupTestAnthropic() {
    const key = document.getElementById('setup-api-key').value.trim();
    const status = document.getElementById('setup-anthropic-status');
    const btn = document.getElementById('setup-test-anthropic');
    if (!key) { document.getElementById('setup-api-key').focus(); return; }
    btn.disabled = true; btn.textContent = 'Testing\u2026';
    status.className = 'setup-status'; status.style.display = 'none';
    try {
      const res = await fetch('/api/setup/key', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({key}),
      });
      const data = await res.json();
      if (data.ok) {
        status.className = 'setup-status ok';
        status.textContent = '\u2713 Connected! Your API key is saved. You can close this guide.';
      } else {
        status.className = 'setup-status err';
        status.textContent = '\u2717 ' + (data.error || 'Connection failed. Check your key and try again.');
      }
    } catch(e) {
      status.className = 'setup-status err';
      status.textContent = '\u2717 Could not reach the server.';
    }
    btn.disabled = false; btn.textContent = 'Save & Test';
  }

  async function setupTestOllama() {
    const status = document.getElementById('setup-ollama-status');
    const btn = document.getElementById('setup-test-ollama');
    btn.disabled = true; btn.textContent = 'Checking\u2026';
    status.className = 'setup-status'; status.style.display = 'none';
    try {
      const res = await fetch('/api/setup/test-ollama');
      const data = await res.json();
      if (data.ok) {
        status.className = 'setup-status ok';
        status.textContent = '\u2713 Ollama is running and the models are ready. You can close this guide.';
      } else {
        status.className = 'setup-status err';
        status.textContent = '\u2717 ' + (data.error || 'Ollama not detected. Make sure it is running and the models are downloaded.');
      }
    } catch(e) {
      status.className = 'setup-status err';
      status.textContent = '\u2717 Could not reach the server.';
    }
    btn.disabled = false; btn.textContent = 'Check connection';
  }

  function setupCopyCmd() {
    const cmd = 'ollama pull qwen2.5:3b && ollama pull nomic-embed-text';
    navigator.clipboard.writeText(cmd).then(function() {
      const btn = document.querySelector('.setup-copy-btn');
      const orig = btn.innerHTML;
      btn.textContent = '\u2713';
      setTimeout(function() { btn.innerHTML = orig; }, 1500);
    });
  }

  // ── Archive modal ─────────────────────────────────────────────────────────
  var _arcStack = [];   // navigation stack: [{type:'root'}, {type:'tree', category, node, path:[]}]

  function openArchive() {
    document.getElementById('archive-overlay').hidden = false;
    switchTab('explore');
    _arcStack = [];
    _arcShowRoot();
  }

  function closeArchive() {
    document.getElementById('archive-overlay').hidden = true;
  }

  document.addEventListener('click', function(e) {
    const ov = document.getElementById('archive-overlay');
    if (ov && e.target === ov) closeArchive();
  });

  function switchTab(name) {
    document.getElementById('tab-explore').classList.toggle('active', name === 'explore');
    document.getElementById('tab-search').classList.toggle('active', name === 'search');
    document.getElementById('panel-explore').classList.toggle('active', name === 'explore');
    document.getElementById('panel-search').classList.toggle('active', name === 'search');
    if (name === 'search') document.getElementById('arc-search-input').focus();
  }

  async function _arcShowRoot() {
    const el = document.getElementById('explore-content');
    el.innerHTML = '<div class="arc-loading">Loading\u2026</div>';
    try {
      const cats = await fetch('/api/archive/categories').then(r => r.json());
      if (!cats.length) {
        el.innerHTML = '<div class="arc-empty">No articles in archive yet.<br>Run an Update Feed first.</div>';
        return;
      }
      let html = '<ul class="arc-cat-list">';
      cats.forEach(function(c) {
        html += '<li class="arc-cat-item" data-cat="'+_esc(c.name)+'">'
          + '<span class="arc-cat-name">'+_esc(c.name)+'</span>'
          + '<span class="arc-cat-count">'+c.count+' article'+(c.count===1?'':'s')+'</span>'
          + '</li>';
      });
      html += '</ul>';
      el.innerHTML = html;
      el.querySelectorAll('.arc-cat-item').forEach(function(item) {
        item.addEventListener('click', function() {
          _arcOpenCategory(item.dataset.cat);
        });
      });
    } catch(e) {
      el.innerHTML = '<div class="arc-empty">Failed to load archive.</div>';
    }
  }

  async function _arcOpenCategory(category) {
    const el = document.getElementById('explore-content');
    el.innerHTML = '<div class="arc-loading">Building tree\u2026 this may take a moment the first time.</div>';
    try {
      const tree = await fetch('/api/archive/tree/'+encodeURIComponent(category)).then(r => r.json());
      if (tree.error) throw new Error(tree.error);
      _arcStack = [{type:'root'}];
      _arcRenderNode(tree, [{label: category, node: tree}]);
    } catch(e) {
      document.getElementById('explore-content').innerHTML =
        '<div class="arc-empty">Failed to load tree: '+_esc(e.message)+'</div>';
    }
  }

  function _arcCountLeaves(node) {
    if (node.articles) return node.articles.length;
    if (node.children) return node.children.reduce(function(s,c){ return s + _arcCountLeaves(c); }, 0);
    return 0;
  }

  function _arcRenderNode(node, breadcrumb) {
    const el = document.getElementById('explore-content');
    let html = '<div class="arc-breadcrumb">';
    html += '<span class="arc-breadcrumb-item" id="arc-bc-root">All categories</span>';
    breadcrumb.forEach(function(crumb, i) {
      html += '<span class="arc-breadcrumb-sep">›</span>';
      if (i < breadcrumb.length - 1) {
        html += '<span class="arc-breadcrumb-item" data-depth="'+i+'">'+_esc(crumb.label)+'</span>';
      } else {
        html += '<span>'+_esc(crumb.label)+'</span>';
      }
    });
    html += '</div>';

    if (node.children && node.children.length) {
      html += '<ul class="arc-node-list">';
      node.children.forEach(function(child, i) {
        const count = _arcCountLeaves(child);
        html += '<li class="arc-node-item" data-child="'+i+'">'
          + '<div class="arc-node-label">'+_esc(child.label)+'</div>'
          + '<div class="arc-node-count">'+count+' article'+(count===1?'':'s')+'</div>'
          + '</li>';
      });
      html += '</ul>';
    } else if (node.articles && node.articles.length) {
      node.articles.forEach(function(a) {
        html += '<a class="arc-article-item" href="'+_esc(a.link)+'" target="_blank" rel="noopener noreferrer">'
          + '<span class="arc-article-title">'+_esc(a.title)+'</span>'
          + '<span class="arc-article-ext">&#8599;</span>'
          + '</a>';
      });
    } else {
      html += '<div class="arc-empty">No articles here.</div>';
    }

    el.innerHTML = html;

    // Breadcrumb navigation
    const rootCrumb = el.querySelector('#arc-bc-root');
    if (rootCrumb) rootCrumb.addEventListener('click', _arcShowRoot);
    el.querySelectorAll('.arc-breadcrumb-item[data-depth]').forEach(function(item) {
      item.addEventListener('click', function() {
        const depth = parseInt(item.dataset.depth, 10);
        const crumb = breadcrumb[depth];
        _arcRenderNode(crumb.node, breadcrumb.slice(0, depth + 1));
      });
    });

    // Child node navigation
    el.querySelectorAll('.arc-node-item').forEach(function(item) {
      item.addEventListener('click', function() {
        const child = node.children[parseInt(item.dataset.child, 10)];
        _arcRenderNode(child, breadcrumb.concat([{label: child.label, node: child}]));
      });
    });
  }

  // Search
  document.addEventListener('keydown', function(e) {
    if (e.key !== 'Enter') return;
    if (e.target.id === 'arc-search-input') arcDoSearch();
  });

  async function arcDoSearch() {
    const q = document.getElementById('arc-search-input').value.trim();
    const el = document.getElementById('arc-search-results');
    if (!q) return;
    el.innerHTML = '<div class="arc-loading">Searching\u2026</div>';
    try {
      const results = await fetch('/api/archive/search?q='+encodeURIComponent(q)).then(r => r.json());
      if (!results.length) {
        el.innerHTML = '<div class="arc-empty">No results found.</div>';
        return;
      }
      let html = '';
      results.forEach(function(r) {
        const date = r.fetched_at ? r.fetched_at.slice(0,10) : '';
        html += '<div class="arc-result-item">'
          + '<div class="arc-result-header">'
          + '<span class="arc-result-title">'+_esc(r.title)+'</span>'
          + (r.link ? '<a class="arc-result-link" href="'+_esc(r.link)+'" target="_blank" rel="noopener noreferrer">Open &#8599;</a>' : '')
          + '</div>'
          + '<div class="arc-result-meta">'
          + '<span class="arc-result-cat">'+_esc(r.category)+'</span>'
          + (date ? '<span class="arc-result-date">'+date+'</span>' : '')
          + '</div>'
          + '</div>';
      });
      el.innerHTML = html;
    } catch(e) {
      el.innerHTML = '<div class="arc-empty">Search failed.</div>';
    }
  }"""


# ── HTML template ─────────────────────────────────────────────────────────────
# Uses __SENTINEL__ placeholders — no Python .format() so braces are safe
_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Claudio &mdash; __DATE__</title>
<style>
__CSS__
</style>
</head>
<body>
<div id="progress-bar"></div>
<div class="page">

  <div id="error-banner">
    <div class="error-body">
      <div class="error-title">Something went wrong</div>
      <div class="error-msg" id="error-msg"></div>
    </div>
    <button class="error-close" onclick="dismissError()" aria-label="Dismiss">&#x2715;</button>
  </div>

  <header>
    <div>
      <div class="report-title">Claudio</div>
      <div class="report-meta">Daily Report &middot; __DATE__ &middot; ~__TIME__m read</div>
    </div>
    <div class="header-right">
      <div class="badges">__BADGES__</div>
      <div class="controls">
        <div class="settings-wrap">
          <button id="settings-btn" onclick="toggleSettings()" title="Model settings">&#9881;</button>
          <div id="settings-popover" class="popover" hidden>
            <div class="popover-title">Model Settings</div>
            <div class="pop-field">
              <label class="pop-label">Provider</label>
              <div class="radio-row">
                <label class="radio-opt"><input type="radio" name="provider" value="anthropic" onchange="onProviderChange()"> Anthropic</label>
                <label class="radio-opt"><input type="radio" name="provider" value="ollama" onchange="onProviderChange()"> Ollama</label>
              </div>
            </div>
            <div class="pop-field">
              <label class="pop-label">Model</label>
              <select id="model-select" class="model-select"></select>
            </div>
            <button id="save-settings-btn" class="save-btn" onclick="saveSettings()">Save</button>
            <a class="pop-setup-link" onclick="openSetup()">First time? Setup guide &rarr;</a>
          </div>
        </div>
        <button id="archive-btn" onclick="openArchive()">
          <span class="btn-icon">&#128269;</span>
          <span>Archive</span>
        </button>
        <button id="manage-btn" onclick="openManage()">
          <span class="btn-icon">&#9776;</span>
          <span>Categories</span>
        </button>
        <button id="update-btn" onclick="triggerUpdate()">
          <span class="btn-icon" id="btn-icon">&#x21BB;</span>
          <span id="btn-label">Update Feed</span>
        </button>
      </div>
    </div>
  </header>

  <div class="categories-grid">
__SECTIONS__
  </div>
</div>

<div id="manage-overlay" class="modal-overlay" hidden>
  <div class="manage-modal">
    <div class="modal-header">
      <span class="modal-title">Manage Categories</span>
      <button class="modal-close" onclick="closeManage()" aria-label="Close">&times;</button>
    </div>
    <div class="modal-body" id="manage-body"></div>
  </div>
</div>

<div id="setup-overlay" class="modal-overlay" hidden>
  <div class="setup-modal">
    <div class="modal-header">
      <span class="modal-title">Setup Guide</span>
      <button class="modal-close" onclick="closeSetup()" aria-label="Close">&times;</button>
    </div>
    <div class="setup-tabs">
      <button class="setup-tab active" id="setup-tab-anthropic" onclick="switchSetupTab('anthropic')">Anthropic API</button>
      <button class="setup-tab" id="setup-tab-ollama" onclick="switchSetupTab('ollama')">Local (Ollama)</button>
    </div>

    <div class="setup-panel active" id="setup-panel-anthropic">
      <div class="setup-step">
        <div class="setup-step-num">1</div>
        <div class="setup-step-body">
          <div class="setup-step-title">Create an Anthropic account</div>
          <div class="setup-step-desc">Go to <a href="https://console.anthropic.com" target="_blank" rel="noopener">console.anthropic.com</a> and sign up for free. New accounts get free credits to get started.</div>
        </div>
      </div>
      <div class="setup-step">
        <div class="setup-step-num">2</div>
        <div class="setup-step-body">
          <div class="setup-step-title">Create an API key</div>
          <div class="setup-step-desc">Once logged in, click <strong>API Keys</strong> in the left sidebar, then click <strong>Create Key</strong>. Give it any name (e.g. "claudio").</div>
        </div>
      </div>
      <div class="setup-step">
        <div class="setup-step-num">3</div>
        <div class="setup-step-body">
          <div class="setup-step-title">Paste your key below</div>
          <div class="setup-step-desc">Copy the key (starts with <code>sk-ant-</code>) and paste it here. It will be saved locally on your computer only.</div>
          <div class="setup-input-row">
            <input class="setup-input" id="setup-api-key" type="password" placeholder="sk-ant-api03-\u2026">
            <button class="setup-test-btn" id="setup-test-anthropic" onclick="setupTestAnthropic()">Save &amp; Test</button>
          </div>
          <div class="setup-status" id="setup-anthropic-status"></div>
        </div>
      </div>
      <div class="setup-step">
        <div class="setup-step-num">4</div>
        <div class="setup-step-body">
          <div class="setup-step-title">Select your model</div>
          <div class="setup-step-desc">Close this guide, click the &#9881; settings icon, choose <strong>Anthropic</strong> as provider and pick a model. <strong>claude-sonnet-4-6</strong> is a good balance of speed and quality.</div>
        </div>
      </div>
    </div>

    <div class="setup-panel" id="setup-panel-ollama">
      <div class="setup-step">
        <div class="setup-step-num">1</div>
        <div class="setup-step-body">
          <div class="setup-step-title">Download Ollama</div>
          <div class="setup-step-desc">Go to <a href="https://ollama.com/download" target="_blank" rel="noopener">ollama.com/download</a> and download the installer for your system (Mac or Windows).</div>
        </div>
      </div>
      <div class="setup-step">
        <div class="setup-step-num">2</div>
        <div class="setup-step-body">
          <div class="setup-step-title">Install and launch it</div>
          <div class="setup-step-desc"><strong>Mac:</strong> open the downloaded file and drag Ollama to Applications, then open it.<br><strong>Windows:</strong> run the installer. Ollama will appear in your system tray when running.</div>
        </div>
      </div>
      <div class="setup-step">
        <div class="setup-step-num">3</div>
        <div class="setup-step-body">
          <div class="setup-step-title">Download the AI model</div>
          <div class="setup-step-desc">Open a Terminal (Mac) or Command Prompt (Windows) and run this command. It downloads the AI model (~2GB, one-time only):</div>
          <div class="setup-code" id="setup-ollama-cmd">ollama pull qwen2.5:3b &amp;&amp; ollama pull nomic-embed-text
            <button class="setup-copy-btn" onclick="setupCopyCmd()" title="Copy">&#128203;</button>
          </div>
        </div>
      </div>
      <div class="setup-step">
        <div class="setup-step-num">4</div>
        <div class="setup-step-body">
          <div class="setup-step-title">Check the connection</div>
          <div class="setup-step-desc">Once the download finishes, click below to verify everything is working:</div>
          <div style="margin-top:0.5rem">
            <button class="setup-test-btn" id="setup-test-ollama" onclick="setupTestOllama()">Check connection</button>
          </div>
          <div class="setup-status" id="setup-ollama-status"></div>
        </div>
      </div>
      <div class="setup-step">
        <div class="setup-step-num">5</div>
        <div class="setup-step-body">
          <div class="setup-step-title">Select Ollama in settings</div>
          <div class="setup-step-desc">Close this guide, click the &#9881; settings icon, choose <strong>Ollama</strong> as provider and pick your model.</div>
        </div>
      </div>
    </div>
  </div>
</div>

<div id="archive-overlay" class="modal-overlay" hidden>
  <div class="archive-modal">
    <div class="modal-header">
      <span class="modal-title">Archive</span>
      <button class="modal-close" onclick="closeArchive()" aria-label="Close">&times;</button>
    </div>
    <div class="archive-tabs">
      <button class="archive-tab active" id="tab-explore" onclick="switchTab('explore')">Explore</button>
      <button class="archive-tab" id="tab-search" onclick="switchTab('search')">Search</button>
    </div>
    <div class="archive-tab-panel active" id="panel-explore">
      <div id="explore-content"></div>
    </div>
    <div class="archive-tab-panel" id="panel-search">
      <div class="arc-search-row">
        <input class="arc-search-input" id="arc-search-input" type="text" placeholder="I remember reading about\u2026">
        <button class="arc-search-btn" onclick="arcDoSearch()">Search</button>
      </div>
      <div id="arc-search-results"></div>
    </div>
  </div>
</div>

<script>
__JS__
</script>
</body>
</html>
"""

_SECTION_TEMPLATE = """\
<section class="category-section">
  <div class="category-heading" style="border-color: __COLOR__">
    <span class="category-dot" style="background: __COLOR__"></span>
    __NAME__
    <span class="category-pct">__PCT__%</span>
  </div>
  <div class="content">
__CONTENT__
  </div>
</section>
"""


def _render(date_str: str, time_str: str, badges_html: str, sections_html: str) -> str:
    return (
        _HTML_TEMPLATE
        .replace("__CSS__", _CSS)
        .replace("__JS__", _JS)
        .replace("__DATE__", date_str)
        .replace("__TIME__", time_str)
        .replace("__BADGES__", badges_html)
        .replace("__SECTIONS__", sections_html)
    )


def render_report(
    report_date: date,
    categories: list[dict],
    reading_time_minutes: int,
) -> str:
    """Render a complete HTML report page."""
    date_str = report_date.strftime("%B %-d, %Y")

    badges_html = "".join(
        f'<span class="badge" style="background:{_PALETTE[i % len(_PALETTE)]}">'
        f'{cat["name"]}: {cat["pct"]}%</span>'
        for i, cat in enumerate(categories)
    )

    sections_html = ""
    for i, cat in enumerate(categories):
        color = _PALETTE[i % len(_PALETTE)]
        content_html = _wrap_articles(
            md.markdown(cat["summary_md"], extensions=["extra"])
        )
        sections_html += (
            _SECTION_TEMPLATE
            .replace("__COLOR__", color)
            .replace("__NAME__", cat["name"])
            .replace("__PCT__", str(cat["pct"]))
            .replace("__CONTENT__", content_html)
        )

    return _render(date_str, str(reading_time_minutes), badges_html, sections_html)


def render_empty_state() -> str:
    """Render the 'no reports yet' page."""
    sections_html = """\
  <div style="flex:1;display:flex;align-items:center;justify-content:center;min-height:60vh;width:100%">
    <div class="empty-state">
      <h2>No report yet</h2>
      <p>Your first report hasn't been generated yet.</p>
      <p class="hint">Click <strong>Update Feed</strong> in the top right corner to get started.</p>
    </div>
  </div>"""
    return _render("No report yet", "&mdash;", "", sections_html)
