# Data sources

Rule: official public APIs only, no scraping. The ingestion program is `insights-sponsors/ingest_content/` (`python -m ingest_content.run`). It is single-threaded, waits about 1 second between requests with backoff on errors, sends the User-Agent `T-Quest-Hackathon/1.0` (no contact details), caches raw responses under `insights-sponsors/data/raw` (gitignored), and is safe to re-run (upserts keyed on source and external id). Every record stores source, `source_url`, license, `retrieved_at`, attribution text and a `commercial_ok` flag. No images are downloaded (URLs only). Short factual fields only. Any fast-fact text we show is hand-written by the team with no LLM involved.

Counts below were computed from the live database on 2026-11-21 after the last ingestion run.

| Source | Items stored | Items linked to a stop (within about 500 m, via SQL) |
|---|---|---|
| Freedom Trail (hand-written, `needs_verify`) | 16 | 16 |
| Analyze Boston: landmarks and historic districts | 102 | 102 |
| Digital Commonwealth (open-rights items only) | 99 | 0 (items have no coordinates) |

Total `stop_content` links: 2,291 (stops include bus stops). Loading-screen facts: 25, hand-written (`needs_verify`).

## Analyze Boston (data.boston.gov)
- Used: CKAN API `https://data.boston.gov/api/3` (`datastore_search`). Datasets: Boston Landmarks Commission landmarks and historic districts. Only records with usable geometry are stored (centroid of the shape, approximate); demolished landmarks and records without a name are skipped.
- Terms: Public Domain Dedication and License (PDDL). We still store attribution: "Contains data from Analyze Boston, City of Boston (PDDL)." `commercial_ok = true`.
- Checked and not used: the `certified-business-directory` dataset is a procurement directory (mostly contractors and services), and its `mbe_wbe_cert` column merges minority-owned and woman-owned, so it cannot support our separate labels. A licensing list has no ownership data.

## Digital Commonwealth
- Used: the official JSON API (`https://www.digitalcommonwealth.org/search.json?q=Boston`), first 5 pages of 50 items. We keep an item only if its rights statement says "No known copyright restrictions" (or the "US" variant) or public domain, and neither its rights nor license text mentions non-commercial, all rights reserved, not evaluated, undetermined or under copyright. 99 items kept from 250 scanned. Stored: id, title, rights text, link. No images. `commercial_ok = true` for the kept items, and the link to the source stays with each item.
- These items have no coordinates, so they are not linked to stops.

## Freedom Trail
- Site names and short original text written by the team, `needs_verify = true`. A human must verify before publishing.

## MBTA
- V3 API and GTFS under the MassDOT Developers License: stops, routes, lines, schedules and live vehicles, predictions and alerts. Row counts and measurements are in `docs/TIGER_DATA_RESULTS.md`.

## Dropped
- A state historic-inventory source was dropped because its terms were unconfirmed. Its code and all its rows were removed.

## Nearby spots and identity labels
- All sponsors, stores, offers and labels are demo placeholders. Boston Red Sox, Mint Julep (43 Brattle St, Cambridge) and Diesel Cafe (257 Elm St, Somerville) carry only the facts we entered: name, address, nearby stop and category. Nothing was copied from Google Places or Google Maps. Demo placeholder. No partnership, endorsement or real discount is implied. Not pursuing real partnerships.
- Label policy: a label (local/independent, woman-owned, African American-owned, Latino-owned, Asian-owned, immigrant-owned, veteran-owned, LGBTQ+-owned, family-owned) may be shown only when (a) the business declared it itself, or (b) an official certification or directory lists it (record the URL). Never inferred from a name, owner's name, photo, review, menu language or by any model. Each label row stores label, status (`declared`, `certified`, `pending`), `evidence_url` or `declaration_note`, `verified_at` and `verified_by`. The database refuses declared or certified rows without evidence. The API reads only the `spot_labels_public` view, so pending labels are never returned and never match a filter.
- Real businesses carry no visible labels in the demo (their only label is `pending`). Filtering is demonstrated on fictional "Sample ... (demo)" spots, whose evidence notes are fictional.
- Per-spot fun facts are hand-written demo text: facts about the three placeholders use only the entered name, address and nearby stop, and the sample spots' facts are labeled fictional.

## Business correction and removal path
All businesses shown are demo placeholders; report any concern to the team. If a listing or label is wrong, we set `nearby_spots.removed_at` (the spot disappears from the API immediately) or change or remove the label rows.

## Before any commercial launch (checklist)
- Replace every demo placeholder with a real, agreed business only after written agreement from that business; until then keep the demo flags.
- Verify every identity label with a declaration or an official listing; no label without evidence.
- Human-verify every `needs_verify` item (Freedom Trail text, loading facts).
- Re-check Digital Commonwealth rights per item at display time and keep the link to the source.
- Add a real public contact for corrections and takedowns.
- Review each source's attribution wording and display it in the apps.
- Review privacy: consent flows, retention (90 days for place visits), rounding of coordinates.
