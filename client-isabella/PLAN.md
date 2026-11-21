# Plan: client-isabella

Default split (see DECISIONS.md; changeable by issue to:client-bryan / to:client-isabella): Bryan = app foundation; Isabella = screens and visual implementation from Figma.

1. Ask humans to drop sketches/Figma into design/ (issue to:humans) if not present
2. Import design tokens into design/tokens/
3. Log each screen in design/INTAKE.md
4. Coordinate the split and component interfaces with client-bryan via issues
5. Then: components and screen build-out exactly as designed

## Status (2026-11-21)
- Done: UI workflow sketch in design/sketches/, palette in design/tokens/colors.json, screens logged in design/INTAKE.md.
- Open: #42 (game-engine ranks), #43 (data-platform travel + facts), #44 (insights-sponsors stores), #45 (humans questions), #10 (split confirmed).
- Framework: React (DECISIONS.md). Design canvas linked in design/FIGMA_LINKS.md.
- Next: confirm web vs native with client-bryan (#10), then components from the canvas.

## Status (2026-11-21, later)
- Approved demo uploaded to design/canvas/ (6 screens), palette and fonts in design/tokens/colors.json.
- Next: build these screens in React from design/canvas/ once client-bryan confirms web vs native (#10).
