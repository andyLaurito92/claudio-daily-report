"""Render the daily report as a self-contained HTML file."""

import re
import markdown as md
from datetime import date

_PALETTE = ["#4a6fa5", "#5e8a5e", "#8b5e6b", "#7a6e4b", "#5e7a8b"]


def _wrap_articles(html: str) -> str:
    """Wrap each h3 + following p(s) in an .article card div; open links in new tab."""
    wrapped = re.sub(
        r"(<h3>.*?</h3>)((?:\s*<p>.*?</p>)+)",
        lambda m: f'<div class="article">{m.group(1)}{m.group(2)}</div>',
        html,
        flags=re.DOTALL,
    )
    # Make all links open in a new tab
    wrapped = re.sub(
        r'<a href="(https?://[^"]+)"',
        r'<a href="\1" target="_blank" rel="noopener noreferrer"',
        wrapped,
    )
    return wrapped


# ── CSS ───────────────────────────────────────────────────────────────────────
# Written with real braces — inserted via str.replace, not .format()
_CSS = """\
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
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
    padding: 1.1rem 1.35rem;
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
  }
  .article h3 a {
    color: #1c1c1e;
    text-decoration: none;
    border-bottom: 1.5px solid #d1d1d6;
    transition: border-color 0.12s;
  }
  .article h3 a:hover { border-color: #555; }
  .article p {
    font-size: 0.93rem;
    color: #4a4a4e;
    line-height: 1.65;
  }
  .article em { color: #8a8a8e; }

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
  .save-btn.saved { background: #5e8a5e; }"""


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
