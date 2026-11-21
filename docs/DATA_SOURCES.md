# Data sources

Rule: official APIs and official bulk downloads only, no scraping. The ingestion program is `insights-sponsors/ingest_content/` (`python -m ingest_content.run`). It is single-threaded, waits about 1 second between requests with backoff on errors, sends a User-Agent naming this project with a contact placeholder (`TODO-contact-placeholder`), caches raw responses under `insights-sponsors/data/raw` (gitignored), and can be re-run safely (upserts keyed on source and external id). Every record stores source, `source_url`, license, `retrieved_at`, attribution text and a `commercial_ok` flag. No images are downloaded (URLs only). Short factual fields only; any fast-fact text we show is hand-written by the team with no LLM involved.

Counts below are from the run on 2026-11-21 against the live Tiger Data database.

| Source | Items stored | Items linked to a stop (within about 500 m, via SQL) | commercial_ok |
|---|---|---|---|
| Freedom Trail (hand-written seed, `needs_verify`) | 16 | 16 | true (our own wording) |
| Analyze Boston: landmarks and historic districts | 102 | 102 | true (PDDL) |
| MHC historic inventory (MACRIS data) | 111 | 111 | false until terms are confirmed |
| Digital Commonwealth (open-rights items only) | 101 | 0 (items have no coordinates) | true for the kept items |

Total `stop_content` links: 4,085 (stops include bus stops). Loading-screen facts: 25 hand-written facts copied from the seed into `loading_facts` (`needs_verify`).

## Analyze Boston (data.boston.gov)
- Used: CKAN API `https://data.boston.gov/api/3` (`package_search`, `package_show`, `datastore_search`). Datasets: Boston Landmarks Commission landmarks (196 records) and historic districts. Only records with usable geometry are stored (centroid of the shape, approximate); demolished landmarks are skipped.
- Terms: PDDL. We still store attribution: "Contains data from Analyze Boston, City of Boston (PDDL)."
- Searched and not found: a public-art dataset (the search returned none). Parks (`open-space`, `park-features`) exist but are not ingested yet.
- Nearby-spots check: `certified-business-directory` (PDDL, 982 rows) is an official City of Boston directory of certified businesses with `mbe_wbe_cert`, `small_local_cert` and `veteran_cert` columns. It is a procurement directory (mostly contractors and services, not storefronts near stops), and `mbe_wbe_cert` merges minority-owned and woman-owned, so it cannot support our separate labels. NOT used. A business that appears there could be offered a label only if it asks us and the directory entry supports exactly that label. `active-food-establishment-licenses` is a licensing list with no ownership data; not used.

## MHC historic inventory (MACRIS data)
- We did NOT scrape mhc-macris.net (its site requires accepting terms). Access: the MAPC-hosted ArcGIS feature service "MHC Historic Inventory Group Layer (from MACRIS)" (`.../MHC_Inventory_GDB/FeatureServer/0`, about 227,573 points), queried per stop with a 500 m spatial filter and only designated resources (`DESIGNATIO` set). Records with no name are skipped (a first run stored 365 blank-title rows, since removed). Stored: MHC number, name, resource type, designation, construction year if present, coordinates, a link back to the MACRIS record.
- Terms: TODO: confirm the terms with MHC and MAPC. Until then `commercial_ok = false` and it is shown only with attribution "Massachusetts Historical Commission (MACRIS), via MAPC ArcGIS feature service."
- Not yet used: the MassGIS bulk download of the MHC inventory.

## Digital Commonwealth
- Used: official JSON API (`https://www.digitalcommonwealth.org/search.json?q=Boston`), first 5 pages of 50 items. Kept only items whose rights statement says "No known copyright restrictions" or public domain: 101 of 250 scanned. Skipped everything else (for example "Rights status not evaluated", Creative Commons NonCommercial, "All rights reserved"). Stored: id, title, rights text, link. No images.
- These items have no coordinates, so they are not linked to stops. Linking them needs a place-name match, which we did not do.

## Freedom Trail
- Hand-written site names and short original text with `needs_verify = true`. A human must verify before publishing.

## MBTA
- V3 API and GTFS under the MassDOT Developers License: stops, routes, lines, schedules and live vehicles, predictions and alerts. See `docs/TIGER_DATA_RESULTS.md` for row counts and measurements.

## Nearby spots and identity labels
- Business names, addresses and nearby stops for the three demo sponsors (Boston Red Sox, Mint Julep, Diesel Cafe) were entered by hand from facts given by the team. Nothing was copied from Google Places or Google Maps. Demo placeholder. No partnership, endorsement or real discount is implied. They are demo placeholders (`demo_placeholder = true`). We are not pursuing real partnerships. "Sample ... (demo)" spots and their labels are fictional.
- Label policy: a label (local/independent, woman-owned, African American-owned, Latino-owned, Asian-owned, immigrant-owned, veteran-owned, LGBTQ+-owned, family-owned) may be shown only when (a) the business declared it itself, or (b) an official certification or directory lists it (record the URL). Never inferred from a name, owner's name, photo, review, menu language or by any model. Each label row stores label, status (`declared`, `certified`, `pending`), `evidence_url` or `declaration_note`, `verified_at` and `verified_by`. The database refuses declared or certified rows without evidence. The API reads only the `spot_labels_public` view, so pending labels are never returned and never match a filter.
- In the demo no real business carries a visible label: Mint Julep and Diesel Cafe hold `local-independent` at status `pending` (never exposed). Filtering is demonstrated on fictional "Sample ... (demo)" spots.

## Business correction and removal path
Any business can ask us to correct or remove its listing or labels. Contact: TODO: contact placeholder (a monitored email address must be set before any public launch). On request we set `nearby_spots.removed_at` (the spot disappears from the API immediately) or change/remove the label rows, and record who did it and when. Corrections to labels need the business's own declaration or an official listing URL.

## Before any commercial launch (checklist)
- Confirm MHC/MAPC terms for the MACRIS-derived data, or drop it.
- Replace the contact placeholder in the ingestion User-Agent and in this document.
- Human-verify every `needs_verify` item (Freedom Trail text, loading facts).
- Check Digital Commonwealth rights per item again at display time; keep the link to the source.
- Not pursuing real partnerships; all sponsors are demo placeholders. If that ever changes, get written agreement from each business first and only then remove its demo flag.
- Verify every identity label with evidence; no label without declaration or official listing.
- Review each source's attribution wording and display it in the apps.
- Review privacy: consent flows, retention (90 days for place visits), and rounding of coordinates.
