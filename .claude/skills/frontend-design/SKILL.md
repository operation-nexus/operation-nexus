---
name: frontend-design
description: Design pass for any new Operation Nexus visual surface (overlay layer, HUD panel, site page, Command Center screen) so it reads as this project and not as a generic template. Use before writing UI code, and when a surface looks like default AI output.
---

# Frontend design (Operation Nexus)

The frontend role card (`.agents/roles/frontend-engineer.md`) makes this pass mandatory. This skill says how to run it.

## 1. Fixed ground (do not re-decide)

- **Subject:** a crowd-commanded C2 "war room" map on a 24/7 live stream (VISION). The audience is a stream viewer
  glancing at a phone or a second monitor, not a user sitting at an app.
- **Hard constraints (OVERLAY spec):** OV-1 five-second readability (text at least 28 px at 1080p, readable at 720p),
  OV-3 colorblind-safe palette with nothing conveyed by colour alone, OV-9 no `innerHTML` and bundled fonts only,
  OV-11 the 9:16 crop. Coalition on the left, enemy on the right. Canvas2D layers plus DOM HUD (ADR-0005).
- **Names and insignia:** fictional only, no real militaries or orgs (Q-PROD-5, Q-NAME-1, Q-NAME-2).
- **Brand:** follow the brand and style guide (NX-274) once it exists. Until the owner picks a direction (Q-BRAND-1),
  present options; do not settle palette or type on your own.

## 2. Process

1. **Plan before code.** Write a compact token set: 4 to 6 named colours (hex), type for 2+ roles (display, body,
   data/mono for numbers and callsigns), a one-sentence layout idea with an ASCII wireframe at 16:9 and 9:16, and the
   one signature element the surface will be remembered by.
2. **Produce 2 or 3 distinct concepts** and compare them against the brief and the constraints above (role card).
3. **Critique against the defaults.** Generated UI clusters around a few looks: cream background with a serif display
   and a terracotta accent; near-black with one acid-green or vermilion accent; hairline-ruled broadsheet columns. For
   a war-room map the obvious default is green-on-black radar. Where the brief leaves a choice free, do not spend it
   on a default; where you keep one, say why it fits.
4. **Build the revised plan exactly,** deriving every colour and size from the tokens. Watch CSS specificity: class
   and element selectors that cancel each other's spacing are a common bug.
5. **Check it rendered:** screenshots at 1080p, 720p and 9:16, the colorblind simulations, keyboard focus and
   `prefers-reduced-motion` on DOM surfaces. Remove one decoration before you call it done.

## 3. Restraint

- Spend boldness in one place, the signature element; keep everything around it quiet.
- Structure encodes truth: numbering, dividers and labels only where the content really is a sequence or a group.
- Motion serves state changes (capture, momentum swing, threat tier), not ambience. The overlay runs 24/7, so
  anything that loops forever must be subtle and cheap (frame budget in the role card).

## 4. Words on screen

- Name things by what the viewer sees and can do (`!join strike`), never by how the system is built.
- Active voice, sentence case, specific over clever. A command keeps one name everywhere: chat, HUD and sitrep.
- Errors and empty states say what happened and what to type next, in the interface's voice. They never apologize.
- Chat and LLM text on screen is moderated and length-capped first (AGENTS.md rule 4).

Record the chosen concept, the alternatives and why in the PR, with screenshots (role card).
