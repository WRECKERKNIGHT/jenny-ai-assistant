# Project-scoped Rules for JENNY AI

## Requirements Clarification & Aligning (MCQ)
Before executing any major code modifications, starting implementation plans, or running CLI changes, you MUST:
1. Formulate 2-3 specific multiple-choice questions (or written questions if highly custom) to present to the user.
2. Ask about details regarding visual styling preferences, transition behavior, API fallbacks, or feature integration scope.
3. Incorporate the user's responses to refine the final output, ensuring zero ambiguity.

## Visual Excellence & Non-Sloppy Code
- Always verify typography, contrast levels, and responsive layouts before finishing a task.
- Double-check canvas render loops to prevent CPU memory leaks or sluggish main-thread animations (e.g. avoid `shadowBlur` in main loops, use pre-calculated radial gradients instead).
