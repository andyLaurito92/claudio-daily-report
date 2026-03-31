Review the current frontend architecture and produce a concrete plan to improve it.

## What to analyze

1. **Read the current state:**
   - `src/renderer.py` — the entire HTML/CSS/JS is hardcoded here as Python strings
   - `src/server.py` — Flask routes, some serving the renderer output, some serving JSON API
   - Any files in `templates/` or `static/` (if they exist)

2. **Identify pain points** in the current approach:
   - CSS/JS embedded as Python strings (no syntax highlighting, no linting, hard to edit)
   - UI changes require re-generating reports (content and shell are coupled)
   - No separation between the "app shell" and "report content"
   - All category management JS is inline strings built with concatenation

3. **Produce a migration plan** covering:

   ### Recommended structure:
   ```
   src/
     templates/
       base.html          ← Jinja2 template with CSS/JS
       report.html        ← extends base, renders category sections
       empty.html         ← extends base, empty state
     static/
       style.css          ← extracted CSS
       app.js             ← extracted JS (settings, update, manage modal)
   ```

   ### Key decisions to surface:
   - Should CSS/JS be served as separate static files (better caching) or inlined (self-contained HTML reports)?
   - Should Flask use Jinja2 templates (already a Flask dependency) or keep Python string rendering?
   - Should reports be fully self-contained HTML files (portable) or require the server to be running?

4. **Estimate effort** for each step (small/medium/large).

5. **Ask the user** which trade-offs they prefer before writing any code.
