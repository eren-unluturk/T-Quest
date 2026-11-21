# Publishing the drafts (Eren, human step)

The builder cannot write `../contracts/`. From the `data-platform/` folder in PowerShell:

```powershell
New-Item -ItemType Directory -Force ../contracts/db | Out-Null
Copy-Item contracts-draft/db/* ../contracts/db/ -Force
Copy-Item contracts-draft/api/data-platform.yaml ../contracts/api/data-platform.yaml -Force
```

Then commit from the repo root. `contracts/db/` and `contracts/api/data-platform.yaml` are in your per-path allowlist (DECISIONS D13), so no `ALLOW_SHARED=1` is needed:

```powershell
cd ..
git add contracts/db contracts/api/data-platform.yaml
git commit -m "Publish data-platform schema v0 and read API draft"
git pull --rebase; git push
```

Before publishing, regenerate `contracts-draft/db/schema.sql` with a real `pg_dump` (see the header of that file).
