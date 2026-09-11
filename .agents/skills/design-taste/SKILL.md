---
name: design-taste
description: Guidelines for premium glassmorphism, curated color palettes, elegant typography hierarchy, and non-sloppy layout aesthetics.
---
# Premium Design Taste Guidelines

1. **Color Scheme & Palette Harmony**:
   - Primary: Obsidian dark modes (`#050508`, `#08080c`).
   - Accents: Curated warm gold (`#ffd700`) and glowing amber, complemented by bright white indicators.
   - Avoid low contrast and mismatched color pairs.
2. **Glassmorphism Formulas**:
   - Background: `rgba(8, 8, 12, 0.75)`
   - Border: `1px solid rgba(255, 215, 0, 0.2)`
   - Backdrop filter: `blur(20px)`
   - Box Shadow: `0 8px 32px rgba(0, 0, 0, 0.5)`
3. **Sleek Layout Alignments**:
   - Give content breathing room using proportional padding (`padding: 16px 20px`).
   - Ensure titlebars, headers, and close buttons are aligned cleanly and don't overlap with custom toolbar items.
4. **Typography Hierarchy**:
   - Display/Headline: `clamp(2rem, 5vw, 3.25rem)` with `font-weight: 600`, letter-spacing `-0.02em`.
   - Body: `0.9375rem`–`1rem`, `line-height: 1.6`, `letter-spacing: 0.01em`.
   - Mono accents (data, metrics, timestamps): `ui-monospace, "SF Mono", Consolas, monospace`.
   - Body text on obsidian backgrounds must reach WCAG AA contrast (`#e8e8ee` or brighter on `#050508`).
5. **Glass Panel Recipe**:
   ```css
   .glass { background: rgba(8, 8, 12, 0.75); border: 1px solid rgba(255, 215, 0, 0.2);
            backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5); }
   ```
   Always ship both `backdrop-filter` and `-webkit-backdrop-filter`.
6. **Accessibility & Motion Respect**:
   - Never convey state with color alone; pair it with icons or text labels.
   - Provide `:focus-visible` rings (2px gold) and honor `prefers-reduced-motion` by disabling slide/flash motion.
