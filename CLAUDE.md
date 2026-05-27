**Project Name:** BTO Calulator
---

## Core Principles

- **Simplicity First**: Minimum code that solves the problem. Nothing speculative. Impact minimal code.
  - No features beyond what was asked.
  - No abstractions for single-use code.
  - No "flexibility" or "configurability" that wasn't requested.
  - No error handling for impossible scenarios.
  - If you write 200 lines and it could be 50, rewrite it.
  - Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.
- **Cost Efficiency**: Same output, minimum tokens. Pick the cheapest path that works.
- **No Laziness**: Find root causes. No temporary fixes. Senior developer standards.
- **Surgical Changes**: Touch only what you must. Clean up only your own mess.
  - Don't "improve" adjacent code, comments, or formatting.
  - Don't refactor things that aren't broken.
  - Match existing style, even if you'd do it differently.
  - If you notice unrelated dead code, mention it — don't delete it.
  - When your changes create orphans: remove imports/variables/functions that YOUR changes made unused. Don't remove pre-existing dead code unless asked.
  - The test: every changed line should trace directly to the user's request.

---

## Workflow Orchestration

### 1. Think and Plan First
- Don't assume. Don't hide confusion. Surface tradeoffs.
- Before implementing:
  - State your assumptions explicitly. If uncertain, ask.
  - If multiple interpretations exist, present them — don't pick silently.
  - If a simpler approach exists, say so. Push back when warranted.
  - If something is unclear, stop. Name what's confusing. Ask.
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions).
- If something goes sideways, STOP and re-plan immediately — don't keep pushing.
- Use plan mode for verification steps, not just building.
- Write detailed specs upfront to reduce ambiguity.

### 2. Subagent Strategy

**Model Delegation** — pick the cheapest model that can handle the job:

| Model  | Use When                                                                                         |
|--------|--------------------------------------------------------------------------------------------------|
| Haiku  | Bulk mechanical tasks, no judgment needed (formatting, renaming, boilerplate, repetitive transforms) |
| Sonnet | Scoped research, code exploration, synthesis, single-file refactors                              |
| Opus   | Real planning, architectural tradeoffs, multi-system reasoning                                   |

**Spawn Rules:**
- Use subagents liberally to keep the main context window clean.
- One task per subagent for focused execution.
- Haiku subagents **never** spawn further subagents. If it needs to, the task was wrong-sized — re-scope it.
- Max spawn depth is **2** (parent → subagent → one more tier).
- If a subagent realises it needs a smarter model, it **returns to the parent** instead of escalating on its own.
- Offload research, exploration, and parallel analysis to subagents.
- For complex problems, throw more compute at it via subagents — but at the right tier.

### 3. Preferred Tools (Token Economy)

Pick the free/cheap option first:

| Task                       | Use This                       | Not This                                  |
|----------------------------|--------------------------------|-------------------------------------------|
| Fetch public web pages     | `WebFetch` (free, text-only)   | Browser tools with screenshots            |
| Dynamic pages / auth walls | `agent-browser` CLI            | Screenshot-based tools (~82% more tokens) |
| Read PDFs                  | `pdftotext`                    | The generic Read tool                     |

- When you find yourself fetching the same way repeatedly, wrap the pattern as a **reusable tool** (bash script or MCP tool).

### 4. Self-Improvement Loop
- After ANY correction from the user: update `tasks/lessons.md` with the pattern.
- Write rules for yourself that prevent the same mistake.
- Ruthlessly iterate on these lessons until mistake rate drops.
- Review lessons at session start for the relevant project.

### 5. Verification Before Done
- Never mark a task complete without proving it works.
- Transform tasks into verifiable goals:
  - "Add validation" → "Write tests for invalid inputs, then make them pass"
  - "Fix the bug" → "Write a test that reproduces it, then make it pass"
  - "Refactor X" → "Ensure tests pass before and after"
- For multi-step tasks, state a brief plan:
  1. [Step] → verify: [check]
  2. [Step] → verify: [check]
  3. [Step] → verify: [check]
- Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.
- Diff behaviour between main and your changes when relevant.
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness.

### 6. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution."
- Skip this for simple, obvious fixes — don't over-engineer.
- Challenge your own work before presenting it.

### 7. Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding.
- Point at logs, errors, failing tests — then resolve them.
- Zero context switching required from the user.
- Go fix failing CI tests without being told how.

---

## Task Management

1. **Plan First**: Write plan to `tasks/todo.md` with checkable items.
2. **Verify Plan**: Check in before starting implementation.
3. **Track Progress**: Mark items complete as you go.
4. **Explain Changes**: High-level summary at each step.
5. **Document Results**: Add review section to `tasks/todo.md`.
6. **Capture Lessons**: Update `tasks/lessons.md` after corrections.

---

## For Python
- Always use `uv` for virtual environments; do not use `venv`.