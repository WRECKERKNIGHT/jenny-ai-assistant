# Project-scoped Rules for JENNY AI

## Requirements Clarification & Aligning (MCQ)
Before executing any major code modifications, starting implementation plans, or running CLI changes, you MUST:
1. Formulate 2-3 specific multiple-choice questions (or written questions if highly custom) to present to the user.
2. Ask about details regarding visual styling preferences, transition behavior, API fallbacks, or feature integration scope.
3. Incorporate the user's responses to refine the final output, ensuring zero ambiguity.

## Skills & Shared Playbooks
Use the bundled project skills before UI work:
- **`.agents/skills/design-taste`** — glassmorphism formulas, obsidian palette, typography hierarchy.
- **`.agents/skills/impeccable-motion`** — spring physics, cubic-bezier curves, canvas render loops.

## Cross-Platform Consistency (Server / Web / Windows / CLI)
- The core HTTP API must stay symmetric across `server.js` (Node) and `windows-version/server.py` (Flask): same route names, same JSON shapes, same `success`/`error` envelope.
- Web dashboards (`public/`) and Windows pages (`windows-version/public/`) share the design system; do not fork the palette per platform.
- CLI (`friday-cli.js`) rules: no silent failures, `--help`/`--version` always available, interactive prompts keep a non-interactive fallback flag.
- Keep committed credential files out of the tree (`.env`, `vault.json`, `settings.json`, `gesture_config.json` defaults are fine; ignore local overrides).

## Visual Excellence & Non-Sloppy Code
- Always verify typography, contrast levels, and responsive layouts before finishing a task.
- Double-check canvas render loops to prevent CPU memory leaks or sluggish main-thread animations (e.g. avoid `shadowBlur` in main loops, use pre-calculated radial gradients instead).

## User Settings Persistence Hardening
- All localStorage/JSON persistence must fail silently and reset to defaults instead of throwing.
- When adding a setting (gesture config, theme, PWA cache) keep the loader tolerant of missing, malformed, or legacy-shaped entries.
