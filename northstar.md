# Hybrid Agent — North Star

## Vision
Build a highly capable, low-cost autonomous assistant that completes complex tasks using my Chrome profile (research, shopping, email, calendar, forms, comparisons, travel, etc). It should be reliable, privacy-respecting, and fast enough on modest hardware while keeping cloud spend minimal. No emojis.

## Operating Principles
1. **Local-first**: Use local vision + deterministic browser primitives; avoid cloud unless blocked.
2. **Single planner pass**: Normalize the user request once, then execute. avoid re-planning loops unless high ROI.
3. **Structured execution**: Favor short, explicit action lists and measurable success criteria.
4. **Safety & privacy**: Never expose secrets; never upload screenshots by default. If escalation requires vision, send summaries not images.
5. **Determinism over cleverness**: Prefer simple, robust steps over fragile “smart” chains.
6. **Token discipline**
7. **Idempotence**: Make actions repeat-safe; detect current page state before acting.

## Scope & Capabilities (current intent)
- Product research and comparisons, availability/price checks, list extraction.
- Email/calendar triage & entry (via my signed-in Chrome profile).
- Account logins, form fill, pagination, downloads only when necessary.
- Multi-page flows with minimal cloud planning.
- Travel planning, flight booking, hotel searches.
- Shopping cart management, order tracking, returns.
- Basic web scraping and data extraction.
- Task automation (scheduled runs, triggers, workflows).

## Architecture (at a glance)
- **Planner (runs once per task)**: Normalize intent → small plan (“go_to_url|click|type|scroll|wait|extract|search_web|analyze_vision”).
- **Local executor**: Drive the browser with primitives and local VLM page understanding.
- **Escalation ladder**: Local → lightweight cloud micro-plan → last-resort bounded steps.
- **Data policy**: Log steps succinctly; redact PII; prefer JSON over prose.

## Cost & Performance Targets
- **Goal**: Complex tasks at a tiny fraction of hosted-agent costs.
- **Default limits**: ≤100 total steps, ≤3 consecutive failures before escalation, cloud calls batched and capped.
- **System constraints**: Optimize for CPU + mid-range GPU (6 GB VRAM).

## Guardrails (File Mutation Policy)
- **PROTECTED — NEVER MODIFY**: anything under the `browser_use` package (installed libs or vendored core), Playwright/Chrome internals, global settings not owned by this repo.
- **Process**: keep PRs small and reversible.

## Execution Rules
- Always read this `NORTH_STAR.md` before coding or browsing.
- Confirm `browser-use >= 0.6.x`. Use my Chrome profile path from config; do not create a fresh profile unless requested.
- Prefer `search_web` APIs over navigating to search engines.
- After any navigation, reassess state via local vision; dismiss common banners safely.
- Never perform purchases or irreversible actions without explicit “ALLOW_TRANSACTION”.

## Success Criteria (per task)
- Clear end condition met (e.g., extracted table, confirmed availability, scheduled entry).
- Short run summary + structured artifact (JSON/CSV/MD) saved to logs.
- Cloud usage and total cost reported; no secrets leaked.

## Roadmap Pointer
- Day-to-day implementation details live in `hybrid_brief.md` (roadmap is mutable). This North Star is the stable contract; do not diverge from it.
