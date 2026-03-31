Apply Socratic maieutics to clarify a feature request or question before acting on it.

**What this does:** Rather than immediately implementing what was asked, this skill helps surface the real need by asking targeted questions — the way Socrates drew out knowledge through dialogue rather than lecturing.

## Process

1. **Read the repo first.** Before asking anything, read the relevant parts of the codebase:
   - `CLAUDE.md` — the project's goals, architecture, and roadmap
   - Any relevant `src/` files related to the request
   - Recent git log: `git log --oneline -10`
   Look for whether the answer already exists, is partially built, or contradicts an existing decision.

2. **Assess clarity.** Ask yourself:
   - Is the request specific enough to implement without assumptions?
   - Does it align with the project's stated goals?
   - Are there multiple valid interpretations?
   - Does it have hidden dependencies or side effects?

3. **If clear and aligned:** Briefly confirm your understanding, then proceed.

4. **If unclear:** Ask ONE focused question at a time — the most important gap. Do NOT ask multiple questions at once. Wait for the answer, then assess again. Repeat until the feature is unambiguous.

   Good question types:
   - "What problem does this solve for you?" (surface the real need)
   - "When you say X, do you mean A or B?" (narrow interpretation)
   - "What should happen when [edge case]?" (uncover implicit requirements)
   - "Is this for today's use or should it scale to [future scenario]?" (scope)

5. **When clear:** Summarize back what you understood in 2-3 sentences, get a yes/no confirmation, then implement.

## Example

User: "I want smarter summaries"

Bad response: immediately changing the summarizer prompt.

Good response:
- Read `src/summarizer.py` and `CLAUDE.md`
- Ask: "What feels wrong about the current summaries — are they too long, too shallow, missing key points, or something else?"
- After answer, ask follow-up if still unclear
- Once clear: "So you want summaries that focus on actionable insights and skip the context-setting intro — max 3 bullets per article. Is that right?" → implement.
