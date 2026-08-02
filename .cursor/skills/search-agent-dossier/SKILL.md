---
name: search-agent-dossier
description: >-
  Search Agent evidence-dossier visual system for HTML mockups, UI prototypes,
  and frontend pages. Dark charcoal surfaces, Instrument Serif + DM Sans, warm
  gold accent, citation-blue links only for sources. Use when designing or
  restyling Search Agent UI, HTML demos/mockups in this product's look, Library
  chrome, brief/report pages, or when the user asks for Search Agent style /
  dossier theme / verifiable-research aesthetic.
---

# Search Agent · Evidence Dossier

Design HTML (and in-repo frontend) in the **evidence dossier** look — not generic AI SaaS, not a dashboard.

**Related skills:** for open-ended visual invention use `frontend-design`; for hi-fi HTML prototypes / variants / slides use `huashu-design`. **This skill wins** when the brief is “look like Search Agent.”

Canonical tokens live in `frontend/app/globals.css` and fonts in `frontend/app/layout.tsx`. Prefer reading those files if they diverge from this skill.

## Aesthetic thesis

> Controllable, verifiable deep research. The UI should feel like a quiet intelligence brief: dark paper, serif brand, muted utility chrome, gold for emphasis, blue reserved for **citable sources**.

One composition per primary viewport. Brand / question / CTA on the home axis — not a control panel.

## Tokens (copy into HTML `:root`)

| Token | Hex | Role |
|-------|-----|------|
| `--bg` | `#0a0c10` | Page ground |
| `--surface` | `#12151c` | Panels / inputs |
| `--surface-raised` | `#181c26` | Raised / active step |
| `--border` | `#2a3040` | Hairlines, input borders |
| `--ink` | `#e8e6e1` | Primary text |
| `--muted` | `#8a909c` | Secondary / utility |
| `--accent` | `#d4a05c` | Emphasis, section labels, CTA fill |
| `--accent-dim` | `#9a7340` | Hover / focus ring |
| `--verify` | `#6ba88a` | Healthy / verified (use sparingly) |
| `--link` | `#7eb8da` | **Citations & source URLs only** |

Atmosphere (body background — keep subtle):

```css
background-image:
  radial-gradient(ellipse 80% 50% at 50% -20%, rgba(212, 160, 92, 0.08), transparent),
  linear-gradient(180deg, #0a0c10 0%, #0d1016 100%);
```

## Typography

| Role | Face | Notes |
|------|------|--------|
| Display / brand / H1 | **Instrument Serif** | Hero brand; report titles; restraint |
| Body / UI | **DM Sans** | Forms, chrome, body copy |
| Mono (keys, progress) | system mono | Settings fields, SSE logs |

Google Fonts (standalone HTML):

```html
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,400&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">
```

```css
--font-display: "Instrument Serif", Georgia, serif;
--font-body: "DM Sans", system-ui, sans-serif;
.font-display { font-family: var(--font-display); }
body { font-family: var(--font-body); color: var(--ink); background: var(--bg); }
```

Eyebrow: `text-xs uppercase tracking-[0.2em]` in `--muted`.  
Section label (report): `0.6875rem`, `letter-spacing: 0.18em`, uppercase, `--accent`.

## Information architecture (chrome)

Match production AppChrome (Wave 12f):

| Zone | Content |
|------|---------|
| Sticky top utility | Right: `Library` + settings gear — **muted**, hover → ink. **Never** `--link` blue for nav |
| Home hero | Eyebrow → serif brand → one support line → input → mode/depth → gold CTA. No Settings/History stack under the title |
| Settings | Right sheet (~420px), not inline expand under hero |
| API status | Silent when healthy; amber top banner only when offline |
| Library | One destination, tabs: Saved / Watching |

Report pages: small wordmark left (via chrome); report title is the only page H1. Citation blue only on `[n]` / source URLs.

## Layout patterns

- Content column: `max-w-3xl` (~48rem) centered; chrome can use `max-w-6xl`
- Radius: modest `rounded-lg` on inputs/panels — not pill soup, not zero-radius broadsheet
- Cards: only when they wrap an interaction or a list row; no card grid in the hero
- Borders: `1px solid var(--border)`; progress = left border accent that turns gold when active
- CTA primary: `background: var(--accent); color: #1a1408; font-semibold`
- Secondary actions: muted text / border buttons

## Motion

Sparse. Prefer: progress line highlight, sheet slide-in, hover color transitions. No glow stacks, no gradient text, no emoji icon rows.

## Hard bans (anti-slop + product-specific)

Do **not**:

- Purple / indigo gradients, Inter-as-display, cream+#terracotta “AI default”
- GitHub-dark + neon cyan/purple glow
- Broadsheet: zero radius + dense newspaper columns (unless user explicitly asks)
- Stack Settings / Saved reports / Watchlist / “API online” under the hero
- Use `--link` for primary navigation
- Dashboard first viewport (stat strips, pill clusters, multi-card hero)
- Emoji as UI icons

## Workflow

1. Confirm deliverable: in-app React vs standalone HTML mockup.
2. Lock tokens + type from this skill (or re-read `globals.css`).
3. Sketch one composition (ASCII ok) before coding.
4. For standalone HTML, start from [html-starter.html](html-starter.html).
5. Self-check: brand first? utility muted? blue only on citations? healthy API silent?

## Copy voice

Plain, operational, sentence case. Errors say what to do (`start-personal.ps1`). No hype (“revolutionary AI”). Product line: *You define the question. We search, extract, and cite every claim.*
