## Build Plan — Phase 5: Versioning & Production Ops

### Goals
- Add ingestion version snapshots, manifests, and rollback capability.
- Establish operations runbooks and backups for indices and artifacts.

### Source of Truth
- `../../docs/INTEGRATION_COMPLETE.md`
- `tools/ops/*`, `artifacts/versions/*`
- `../../Build_plan_README/completed/*`

### Prerequisites
- Phase 4 completed

### Steps
1) Create a new version snapshot
```powershell
python tools/ops/create_version.py --source artifacts/ingestion_production --out artifacts/versions --desc "Production baseline"
```

2) Run production ingestion with versioning
```powershell
python tools/ops/run_production_ingest.py --source data/raw --out artifacts/ingestion_production --version
```

3) Backup indices
- Weaviate: snapshot API / Docker volume backup
- OpenSearch: snapshot repository (filesystem) and snapshot job

4) Rollback procedure (dry-run)
```powershell
python tools/ops/rollback_version.py --version v1.0_prod --dry-run
```

### Validation
- New version folder created with manifest and artifacts
- Indexes consistent with manifest counts

### KPIs (Phase Exit)
- Reproducible ingestion (same doc counts, hashes)
- Rollback verified in dry-run

### Troubleshooting
- Missing permissions on snapshot paths → run as admin, verify Docker volume mapping

### References
- `../../docs/INTEGRATION_COMPLETE.md`
- `tools/ops/*`
