# Control Surface — Design System

**Purpose:** this is the document that governs *how it looks*, written so that an AI model (or a human) building this interface produces something that reads as a deliberately designed professional instrument, not a generated template. It is not optional decoration guidance — every rule below is either grounded in `00_RESEARCH_BASIS.md` or in FRACTAL-FLOW's own specific architecture, and every rule exists to rule something out.

---

## 1. Subject grounding (read before anything else)

This is not "a dashboard." It is **an operator's instrument panel for a hierarchical, rule-based, multi-timeframe trading system** — the visual language should come from that specific system, not from "fintech" in general. Two things make FRACTAL-FLOW specifically identifiable, and both should become actual visual devices rather than staying abstract:

1. **The timeframe cascade** (4H → 1H → 30M → 15M → 5M → 1M) is the system's own structural backbone. It becomes a real UI element (§7), not just a data column.
2. **The eleven-gate chain** (Q∧E∧R∧P∧L∧O∧T∧N∧K∧A∧X) is the system's own decision architecture. It becomes a real, glanceable status strip (§7), not buried in a log.

These two elements are this design's **one bold, memorable thing** (per the frontend-design skill's restraint principle) — spend the design's boldness there, and keep everything else (panel chrome, tables, typography) quiet and disciplined around them.

---

## 2. Color tokens

Reserved almost entirely for *state*, per research basis §4 — not for brand decoration. Named, specific values (not a generic palette-generator output):

| Token | Hex | Role |
|---|---|---|
| `bg.base` | `#0A0E14` | App background — a deep blue-black, not pure black or warm cream. Evokes a night session without reaching for a literal "dark mode" cliché. |
| `bg.panel` | `#10151D` | Panel/card surface, one step up from base. |
| `bg.raised` | `#161C26` | Hover/active surface, inputs. |
| `border.hairline` | `#232A35` | All panel and table borders — 1px, always. No soft shadows anywhere in this system (see §5). |
| `text.primary` | `#E7EAEE` | Primary text — a cool off-white, not pure `#FFF`. |
| `text.muted` | `#6E7A8A` | Labels, secondary text, timestamps. |
| `text.faint` | `#454E5C` | Disabled, placeholder, structural chrome. |
| `signal.long` | `#4FAE86` | Long/positive/profit. Muted teal-green — deliberately *not* neon/acid-green (the AI-tell) and *not* the `#00D4AA` cyan already used by an existing named trading-terminal template. |
| `signal.short` | `#C25B6B` | Short/negative/loss. Muted rose, chosen to sit clearly apart from both the terracotta AI-tell (`~#D97757`) and generic bright coral. |
| `status.warning` | `#BFA13B` | Degraded, approaching a limit, CANARY-stage calibration. Muted gold, not bright yellow. |
| `status.critical` | `#B23B3B` | Kill-switch active, fence mismatch, authentication failure. Deep red, reserved for genuinely critical states only — never reused for ordinary negative P&L (that's `signal.short`). |
| `accent.focus` | `#5B8FBF` | The *only* non-semantic accent: focus rings, active-tab underline, the selected-lane highlight. A muted slate-blue, used sparingly enough that it never competes with the signal colors. |

**Rule:** no gradient appears anywhere in this system. No box-shadow appears anywhere in this system — elevation is communicated by the `bg.panel`/`bg.raised` step and the hairline border, never by a blurred shadow. This directly rules out AI-tell #4 (the SaaS-card kit) and is independently correct for the subject (research basis §1-2).

---

## 3. Typography

| Role | Typeface | Why |
|---|---|---|
| UI labels, prose, navigation | **IBM Plex Sans** | A grotesk designed for enterprise technical software — fits an operator tool's actual vernacular rather than a marketing-page default. Not Inter (now itself a default-by-overuse), not a display serif (wrong register for this subject). |
| All numeric/data values: prices, sizes, P&L, R-multiples, timestamps, hashes, IDs, log lines | **IBM Plex Mono** | Same type family as the UI face (designed together, so pairing them doesn't read as a mismatched grab-bag), used *functionally* per research basis §3 — tabular alignment for scanning columns of numbers, and a real signal that "this is raw system data" versus a written label. Never used for a generic "techy" label — that misuse is itself a named AI-tell. |

**Type scale:** a deliberate, restrained scale — `11px` (dense table data, the default density), `13px` (body/labels), `15px` (panel headers), `20px` (the one or two numbers per screen that deserve emphasis — e.g. total equity, daily P&L), `28px` (used exactly once per screen, if at all, for the single most important number in view). No large display headline anywhere in this system — this is an instrument, not a hero page.

**Explicitly forbidden**, per the frontend-design skill's own named tells, applied here:
- No tracked-out ALL-CAPS eyebrow label above anything.
- No accenting a single word in a sentence via italic/bold/color.
- No unnecessary label-above-content pattern — a number's unit and meaning come from its column header or adjacent label, once, not repeated as a floating tag.
- No middle-dot-joined meta strings (`A · B · C`), no spaced-em-dash labels (`WORD — fragment`), no arrow (`→`) appended to buttons or links.
- IBM Plex Mono is used **only** for the data roles listed above — never for a UI label just to look "technical."

---

## 4. Layout

```
┌─ header: lane selector · connection/health dot · user/role ──────────────┐
├─ gate-chain strip (signature element, §7) ────────────────────────────────┤
├───────────────┬────────────────────────────────────────┬─────────────────┤
│  nav rail      │   primary panel (positions / decisions /  │  context panel   │
│  (icon+label,  │   health / calibration — tab-selected,    │  (selected       │
│  persistent,   │   dense table, 11-13px data rows)          │  position/lane   │
│  left, ~64px)  │                                             │  detail; MAE/MFE │
│                │                                             │  path; timeframe │
│                │                                             │  cascade, §7)    │
├───────────────┴────────────────────────────────────────┴─────────────────┤
│  footer: notification ticker (most recent, scrolling-on-demand not auto)  │
└────────────────────────────────────────────────────────────────────────────┘
```

- **Alignment:** left-aligned throughout. No centered hero section — this is a working screen, not a landing page (ruling out AI-tell #1's "default big-number-with-small-label-and-gradient-accent" hero treatment by having no hero at all).
- **Grid:** a strict 8px spacing unit; panel padding `12px`, table row height `28px` at default density (a "comfortable" density option exists per `01_ARCHITECTURE.md` §6 but is not the default — density-first per research basis §1).
- **Borders, not cards:** panels are separated by `border.hairline` 1px rules, not by distinct rounded, shadowed cards. `border-radius` is `0` on every data surface (tables, panels); a single `2px` radius is permitted only on small interactive controls (buttons, inline-keyboard-equivalent GUI chips) — just enough to read as touchable, never enough to read as "card."

---

## 5. Motion

Per the frontend-design skill's explicit guidance (scattered hover transitions and fade-slide-ins on every card are a named AI tell): **motion in this system only answers a user's action or reports a real state change.**
- A value that updates live (price, P&L) changes with a brief, subtle flash of `signal.long`/`signal.short` background tint that decays over ~400ms — this communicates "this number just moved," which is real information, not decoration.
- Opening a confirmation dialog/inline-keyboard-equivalent: a simple, fast (150ms) opacity+8px transition — nothing bounces, nothing staggers.
- No entrance animation on page load. No hover-lift on table rows. No skeleton-shimmer loading states that run longer than the data actually takes to arrive — if data is slow, say so (per `01_ARCHITECTURE.md` §7's "fast failure visibility" rule), don't disguise it with decorative shimmer.

---

## 6. Status and signal components

- **Status pill:** a small, solid-color (not gradient) rounded-`2px` tag with white/near-white text, used only for the four-state vocabulary `OK / WARNING / CRITICAL / OFFLINE` (mapping to `signal.long`-adjacent neutral green, `status.warning`, `status.critical`, `text.faint`-on-`bg.raised`). Never used for arbitrary labels — if you're reaching for a pill for something that isn't one of these four states, it's the wrong component.
- **Connection/health dot:** a single 6px dot in the header, filled with the same four-state vocabulary — the fastest-glance element in the whole system, deliberately tiny and unremarkable until it turns `status.critical`, at which point its size doubles. This is the one place a state change is allowed to visibly grow, because it's reporting something the operator must not miss.
- **Tables, not cards, for lists.** Positions, decisions, orders — always a dense table with a sortable header row, never a repeated card layout. Cards are reserved for exactly one thing: the handful of top-level summary numbers in the header strip (equity, daily P&L, open risk) — three to five numbers, each with a one-line `text.muted` label beneath, no icon, no accent border, no gradient.

---

## 7. Signature elements (the one bold thing, spent deliberately)

### 7.1 Gate-chain strip
Eleven small cells, one per gate letter (`Q E R P L O T N K A X`), shown for the currently-selected opportunity or position. Each cell is a single letter in `text.mono`, with its background one of: `signal.long`-tinted (passed), `status.critical`-tinted (failed — and this is the *only* reason a trade didn't happen, shown structurally rather than buried in a log line), or `text.faint` (not yet evaluated / not applicable). Hovering (GUI) or a `/decisions` detail view (Telegram, as a formatted text row) shows the reason string for any failed gate. This is directly derived from FRACTAL-FLOW's own gate-chain architecture (`docs/00_CONSTITUTION.md`) — no other trading dashboard has this exact element, because no other system's decision architecture is shaped this way.

### 7.2 Timeframe cascade indicator
A small horizontal strip `4H 1H 30M 15M 5M 1M`, with the timeframe currently driving the active decision/migration highlighted in `accent.focus` and the others in `text.muted` — visually showing the system's own hierarchical migration (e.g. a runner that has migrated its trailing anchor from 5M to 15M per `docs/15_POSITION_MANAGEMENT.md`) as a glanceable strip rather than a sentence of prose. Appears in the context panel for any selected position.

**These two elements are the design's memorable signature.** Everything else in this document exists to keep the rest of the interface quiet enough that they read as intentional, not as two more widgets among many.

---

## 8. Telegram bot "design system" (the same discipline, in a medium with no CSS)

A chat interface has no color tokens or layout grid, but the same principles translate into concrete formatting rules:

- **Monospace for data, bold for labels, nothing else.** Telegram's `MarkdownV2`/HTML formatting is used exactly the way §3's type system is used: numbers and IDs in a monospace code span, labels in plain bold, prose unstyled. No italics, no strikethrough, no block quotes used as decoration.
- **A fixed, small, meaning-tied emoji vocabulary — not decoration.** Exactly four status emoji, reused consistently and never substituted for variety: 🟢 (OK/long), 🔴 (critical/short), 🟡 (warning), ⚪ (offline/not applicable) — the same four-state vocabulary as the GUI's status pill (§6), so a user who knows the GUI immediately reads the bot the same way. No other emoji anywhere in bot output — not in headers, not as bullet points, not as flourish. This is a deliberate, narrow rule specifically to avoid the generic "AI chatbot" feel of liberal decorative emoji use.
- **Message shape is fixed per command**, not freely generated prose — `/status` always renders the same field order, so a returning user's eye knows exactly where to look without reading the whole message, mirroring the GUI's persistent panel layout (research basis §5's "the next action should never require thinking").
- **Confirmations always edit the triggering message in place** (inline keyboard → edited result), never send a new message for a result the user is actively waiting on, per research basis §5-6.
- **The gate-chain and timeframe-cascade signature elements (§7) get a text rendering** for `/decisions` detail views: `Q🟢 E🟢 R🟢 P🟢 L🔴(congested) O⚪ T⚪ N⚪ K⚪ A⚪ X⚪` on one monospace line — the same information architecture as the GUI strip, translated rather than redesigned.

---

## 9. Explicit pre-build checklist

Before implementing any screen or bot message, confirm:
- [ ] No gradient, no box-shadow, no rounded card for a data surface.
- [ ] No ALL-CAPS eyebrow, no single-word-accented headline, no middle-dot meta string, no spaced-em-dash label, no trailing `→`.
- [ ] Monospace used only for data values, never for a UI label chosen "to look technical."
- [ ] Color used only for the defined semantic states in §2/§6 — never as unexplained brand decoration.
- [ ] Every animation answers a specific state change or user action; nothing fades/slides in on load.
- [ ] Telegram output uses only the four-emoji vocabulary, and only for status — never decoratively.
- [ ] The gate-chain strip and timeframe cascade are present wherever a position/opportunity is in detailed view — these are the signature, and their absence makes the screen generic again.
