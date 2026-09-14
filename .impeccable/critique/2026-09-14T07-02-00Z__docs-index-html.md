---
target: HTML and PowerPoint SDK workshop decks
total_score: 22
max_score: 32
na_heuristics: 5,9
p0_count: 0
p1_count: 3
timestamp: 2026-09-14T07-02-00Z
slug: docs-index-html
---
Method: dual-agent (A: 733bb9d2-b1a0-4a27-a053-5732909d65ab · B: 42265914-aa56-4112-8319-132ee430547c)

## Design Health

| Heuristic | HTML | PPTX | Finding |
|---|---:|---:|---|
| Status and progress | 3 | 2 | HTML has dots and numbering; neither has section-level progress. |
| Match to developer reality | 3 | 3 | Strong language, but several claims are too absolute or stale. |
| User control | 3 | 2 | HTML supports keys, touch and direct slide buttons; PPTX is linear. |
| Consistency | 3 | 3 | Each deck is coherent alone, but the two decks disagree on curriculum and facts. |
| Recognition over recall | 2 | 2 | Concepts are introduced long before their runnable examples. |
| Efficiency | 3 | 1 | HTML has multiple navigation paths; PPTX has no visible section navigation. |
| Minimalism | 2 | 2 | Repeated grids, duplicate concept/sample passes and dense code reduce focus. |
| Help and sources | 3 | 2 | HTML links sources; PPTX often hides qualifications in notes. |
| **Total** | **22/32** | **17/32** | **Both need structural simplification before polish.** |

Heuristics 5 and 9 are not applicable to these static reading surfaces.

## Specificity verdict

The HTML deck is the visual authority: Primer dark colors, repository chrome,
Mona Sans/JetBrains Mono, code windows and progress treatment feel authored
for GitHub developers. The PPTX shares the palette but relies too heavily on
Calibri, equal-weight icon grids and dense code blocks.

The deterministic HTML scan found three signals: `overused-font`,
`codex-grid-background`, and `em-dash-overuse`. The first two are contextual
false positives: Mona Sans is GitHub-specific and the background is a radial
dot field, not a generic line grid. The em-dash count is a real aggregate copy
signal and should be reduced while editing.

## What works

- Strong GitHub-native visual identity in HTML.
- Responsible emphasis on detach versus delete, timeouts, MCP auth, tool scope
  versus sandboxing, and host-owned production responsibilities.
- Runnable samples, source links and Codespaces make the material actionable.

## Priority issues

### P1 — Double-pass curriculum

Tools, custom tools, agents, hooks and MCP are taught as concept slides, then
again as sample slides. The first runnable example arrives at 17/30 in HTML and
21/28 in PPTX.

**Fix:** reach a successful session by slide 6–7, then alternate concept,
minimal code and expected result.

### P1 — No canonical curriculum

HTML promises eight samples while PPTX still says seven, hard-codes
`gpt-5-mini`, uses legacy-first HITL and has a stale audit date. PPTX
foregrounds MAF/system prompts; HTML foregrounds sandbox/lifecycle updates.

**Fix:** one shared 24-slide core and one stable v1.0.13 baseline.

### P1 — Projector readability

PPTX contains 7–13 pt runs and full prototypes; HTML's HITL/release slides are
also too dense.

**Fix:** 10–12 meaningful code lines per slide, visible caveats beside claims,
and separate structured input, exact approval and sandbox bypass.

### P2 — Caveats live in notes

Critical truths such as host-owned tenant isolation and tool scope not being a
sandbox are often visually subordinate while `approve_all` dominates code.

**Fix:** show each boundary next to the corresponding code or claim.

### P2 — Weak ending

Release history, MAF and system-prompt details appear after the practical CTA.

**Fix:** move optional integrations/history out of the core and end immediately
after the launch checklist.

## Persona red flags

**Jordan (first-time SDK user):** must memorize too many primitives before
seeing one successful call; likely to confuse hooks, permissions and sandbox.

**Alex (experienced developer):** will skip duplicated concept slides and lose
confidence when HTML/PPTX disagree on sample count, model choice and HITL.

**Sam (presentation-distance/low-vision):** cannot reliably read the PPTX code
and muted detail text from the back of a room.

## Target curriculum

1. Title
2. Workshop contract
3. Why the SDK
4. Architecture
5. Get to green
6. Canonical session skeleton
7. Example 01 streaming
8. Example 02 custom tool
9. Tool taxonomy
10. Exposure vs permission vs sandbox
11. Example 03 custom agents
12. Example 04 hooks
13. Example 05 MCP
14. Example 06 persistence
15. HITL mental model
16. Example 07A structured elicitation
17. Example 07B exact-action approval
18. Example 08 sandbox
19. Multi-user identity
20. BYOK
21. Deployment choices
22. Production responsibilities
23. Run it now
24. Closing/Q&A
