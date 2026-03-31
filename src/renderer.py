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

  /* ── Category list items ── */
  .cat-item {
    border: 1.5px solid #e5e5ea; border-radius: 10px;
    margin-bottom: 0.75rem; overflow: hidden;
  }
  .cat-header {
    display: flex; align-items: center; gap: 0.6rem;
    padding: 0.75rem 1rem; background: #fafafa;
  }
  .cat-color-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
  .cat-name { font-weight: 600; font-size: 0.9rem; color: #1c1c1e; flex: 1; }
  .cat-weight-badge {
    font-size: 0.72rem; color: #6b6b6b; background: #e5e5ea;
    padding: 0.15rem 0.5rem; border-radius: 999px;
  }
  .cat-actions { display: flex; gap: 0.3rem; margin-left: 0.3rem; }
  .cat-action-btn {
    background: none; border: none; cursor: pointer; color: #8a8a8e;
    font-size: 0.85rem; padding: 0.25rem 0.4rem; border-radius: 5px;
    transition: background 0.12s, color 0.12s;
  }
  .cat-action-btn:hover { background: #f0f0f5; color: #1c1c1e; }
  .cat-action-btn.delete:hover { background: #fff5f5; color: #b91c1c; }
  .cat-body { padding: 0.65rem 1rem 0.75rem; border-top: 1px solid #f0f0f5; }
  .cat-desc { font-size: 0.82rem; color: #6b6b6b; margin-bottom: 0.65rem; }
  .source-list { margin: 0; padding: 0; list-style: none; }
  .source-item {
    display: flex; align-items: center; gap: 0.5rem; padding: 0.3rem 0;
    font-size: 0.78rem; color: #3a3a3c;
    border-bottom: 1px solid #f5f5f7;
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
  .add-source-row { display: flex; gap: 0.5rem; margin-top: 0.5rem; align-items: center; }
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
  // Enter key on add-source inputs (delegated, avoids inline string escaping)
  document.addEventListener('keydown', function(e) {
    if (e.key !== 'Enter') return;
    var inp = e.target;
    if (!inp.classList.contains('add-source-input')) return;
    var row = inp.closest('.cat-item');
    if (!row) return;
    _mgrAddSrc(parseInt(row.dataset.idx, 10));
  });

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

  function _renderMgr() {
    const body = document.getElementById('manage-body');
    const total = _mgrCats.reduce(function(s,c){ return s + (c.weight||1); }, 0);
    var html = '';
    _mgrCats.forEach(function(cat, i) {
      const pct = total > 0 ? Math.round((cat.weight||1) / total * 100) : 0;
      const color = _MGR_PALETTE[i % _MGR_PALETTE.length];
      const sources = cat.sources || [];
      html += '<div class="cat-item" data-idx="'+i+'">';
      html += '<div class="cat-header">';
      html += '<span class="cat-color-dot" style="background:'+color+'"></span>';
      html += '<span class="cat-name">'+_esc(cat.name)+'</span>';
      html += '<span class="cat-weight-badge">'+pct+'%\u00b7w'+_esc(cat.weight)+'</span>';
      html += '<div class="cat-actions">';
      html += '<button class="cat-action-btn" onclick="_mgrEditCat('+i+')" title="Edit">&#9998;</button>';
      html += '<button class="cat-action-btn delete" onclick="_mgrDeleteCat('+i+')" title="Delete">&#215;</button>';
      html += '</div>';
      html += '</div>';
      html += '<div class="cat-body">';
      if (cat.description) html += '<div class="cat-desc">'+_esc(cat.description)+'</div>';
      html += '<ul class="source-list">';
      sources.forEach(function(src, si) {
        html += '<li class="source-item">';
        html += '<span class="source-url" title="'+_esc(src.url)+'">'+_esc(src.url)+'</span>';
        html += '<button class="source-remove-btn" onclick="_mgrRemoveSrc('+i+','+si+')" title="Remove">&#x2715;</button>';
        html += '</li>';
      });
      html += '</ul>';
      html += '<div class="add-source-row">';
      html += '<input class="add-source-input" id="src-in-'+i+'" type="url" placeholder="https://example.com/feed.rss">';
      html += '<button class="add-source-btn" onclick="_mgrAddSrc('+i+')">Add RSS</button>';
      html += '</div>';
      html += '</div>';
      html += '</div>';
    });
    html += '<div class="add-cat-section" id="add-cat-section">';
    html += '<button class="add-cat-btn" onclick="_mgrShowAddForm()">+ Add Category</button>';
    html += '</div>';
    body.innerHTML = html;
  }

  function _mgrEditCat(idx) {
    const cat = _mgrCats[idx];
    const item = document.querySelector('.cat-item[data-idx="'+idx+'"]');
    if (!item) return;
    item.innerHTML = '<div class="edit-form">'
      + '<div class="edit-row">'
      + '<div class="edit-field"><label class="edit-label">Name</label>'
      + '<input class="edit-input" id="ed-name-'+idx+'" value="'+_esc(cat.name)+'"></div>'
      + '<div class="edit-field weight-field"><label class="edit-label">Weight</label>'
      + '<input class="edit-input" id="ed-wt-'+idx+'" type="number" min="1" value="'+_esc(cat.weight)+'"></div>'
      + '</div>'
      + '<div class="edit-row">'
      + '<div class="edit-field"><label class="edit-label">Description</label>'
      + '<input class="edit-input" id="ed-desc-'+idx+'" value="'+_esc(cat.description||'')+'"></div>'
      + '</div>'
      + '<div class="edit-actions">'
      + '<button class="edit-cancel-btn" onclick="_loadMgrCats()">Cancel</button>'
      + '<button class="edit-save-btn" onclick="_mgrSaveCat('+idx+')">Save</button>'
      + '</div></div>';
    document.getElementById('ed-name-'+idx).focus();
  }

  async function _mgrSaveCat(idx) {
    const name = document.getElementById('ed-name-'+idx).value.trim();
    const weight = parseInt(document.getElementById('ed-wt-'+idx).value) || 1;
    const description = document.getElementById('ed-desc-'+idx).value.trim();
    if (!name) { document.getElementById('ed-name-'+idx).focus(); return; }
    try {
      await fetch('/api/categories/'+idx, {
        method: 'PUT',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({name, weight, description}),
      });
      await _loadMgrCats();
    } catch(e) { showError('Failed to save category.'); }
  }

  async function _mgrDeleteCat(idx) {
    const cat = _mgrCats[idx];
    if (!confirm('Delete category "'+cat.name+'"? This cannot be undone.')) return;
    try {
      await fetch('/api/categories/'+idx, {method:'DELETE'});
      await _loadMgrCats();
    } catch(e) { showError('Failed to delete category.'); }
  }

  async function _mgrAddSrc(idx) {
    const input = document.getElementById('src-in-'+idx);
    const url = input.value.trim();
    if (!url) { input.focus(); return; }
    try {
      await fetch('/api/categories/'+idx+'/sources', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({url, type:'rss'}),
      });
      await _loadMgrCats();
    } catch(e) { showError('Failed to add source.'); }
  }

  async function _mgrRemoveSrc(idx, srcIdx) {
    try {
      await fetch('/api/categories/'+idx+'/sources/'+srcIdx, {method:'DELETE'});
      await _loadMgrCats();
    } catch(e) { showError('Failed to remove source.'); }
  }

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
      + '<button class="edit-cancel-btn" onclick="_renderMgr()">Cancel</button>'
      + '<button class="edit-save-btn" onclick="_mgrSaveNew()">Add</button>'
      + '</div></div>';
    document.getElementById('nc-name').focus();
  }

  async function _mgrSaveNew() {
    const name = document.getElementById('nc-name').value.trim();
    const weight = parseInt(document.getElementById('nc-wt').value) || 1;
    const description = document.getElementById('nc-desc').value.trim();
    if (!name) { document.getElementById('nc-name').focus(); return; }
    try {
      await fetch('/api/categories', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({name, weight, description}),
      });
      await _loadMgrCats();
    } catch(e) { showError('Failed to add category.'); }
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
    # Wrap in a single flex column so the grid layout still works
    sections_html = """\
  <div class="category-section" style="flex:unset;align-items:center;justify-content:center">
    <div class="empty-state">
      <h2>No report yet</h2>
      <p>Your first report hasn't been generated yet.</p>
      <p class="hint">Click <strong>Update Feed</strong> in the top right corner to get started.</p>
    </div>
  </div>"""
    return _render("No report yet", "&mdash;", "", sections_html)
