# future-hosting

UNTESTED, and not part of the demo. The T-Quest demo runs locally (see `docs/DEMO.md`). These files were prepared for a public deployment that we decided to defer. Nothing here has been deployed, built or run end to end.

| Path | What it is |
|---|---|
| `docker/*.Dockerfile` | One image per backend (data-platform, insights-sponsors, game-engine). Never built: Docker was not available. Build context is the repo root. |
| `docker/dockerignore.txt` | The `.dockerignore` for those builds. Copy it to the repo root as `.dockerignore` before building. |
| `vercel.json` | Security headers for the web app on Vercel. Move it back to `web/` to use it. |
| `scripts/seed-demo-db.mjs` | Seeds a separate demo database. Wrapper around `python -m data_platform.seed_demo`, which still lives in `data-platform/src/data_platform/seed_demo.py` (with its unit test) because moving it would break the package import. |

The full checklist is in [docs/FUTURE_PUBLIC_HOSTING.md](../docs/FUTURE_PUBLIC_HOSTING.md).

A restricted database role (a database account that reads the live data and writes only demo rows) was prototyped and then removed. It does not exist in the repo or the database.
