# Plan: client-bryan

Default split (see DECISIONS.md; changeable by issue to:client-bryan / to:client-isabella): Bryan = app foundation; Isabella = screens and visual implementation from Figma.

1. Wait for sketches/Figma in design/ (do not choose a framework before then)
2. Log each sketch/screen in design/INTAKE.md with the API it implies
3. Request OpenAPI contracts from each service (issue to:data-platform, to:insights-sponsors, to:game-engine)
4. Propose framework choice by issue to to:humans once the sketches show what is needed
5. Then: shell + navigation, generated API client, state layer, auth/session, location/map plumbing
