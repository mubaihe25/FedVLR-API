# FedVLR-API

`FedVLR-API` is the backend service for the FedVLR competition demo. It connects the frontend training console with the `FedVLR` algorithm repository, provides experiment launch and status polling, and exposes historical experiment outputs for analysis pages.

## Current Responsibilities

- health check;
- capability matrix and unified experiment schema access;
- experiment launch through `FedVLR/scripts/launch_experiment.py`;
- validate-only and dry-run checks without starting training;
- asynchronous launch status polling;
- historical result scanning from `FedVLR/outputs/results`;
- single-experiment summary, result, and CSV download;
- showcase comparison data for demo pages;
- read-only showcase artifact APIs for exported scenario reports under `FedVLR/outputs/showcase_artifacts`.

This service is not a production task platform. The launch registry is stored in process memory, so service restart loses launch status records. There is currently no database, authentication system, production queue, or durable task scheduler.

## Repository Layout

```text
app/
  core/
    settings.py          environment and path resolution
  models/
    schemas.py           request/response models
  routes/
    capabilities.py      capability matrix and experiment schema endpoints
    experiments.py       launch, status, summary, result, csv endpoints
    health.py            health endpoint
    showcase.py          showcase comparison and artifact endpoints
  services/
    capability_store.py  reads FedVLR capability/schema files
    launcher_service.py  writes temp configs and starts FedVLR subprocesses
    launch_registry.py   in-memory launch records
    result_store.py      scans FedVLR output JSON/CSV files
    showcase_store.py    scans and reads exported showcase artifacts
  main.py                FastAPI app
```

## Environment Variables

- `FEDVLR_ROOT`: optional path to the `FedVLR` repository. Defaults to `../FedVLR` relative to this repository.
- `FEDVLR_RESULTS_DIR`: optional path to the results directory. Defaults to `<FEDVLR_ROOT>/outputs/results`.
- `SHOWCASE_ARTIFACT_ROOT`: optional path to exported showcase artifacts. Defaults to `<FEDVLR_ROOT>/outputs/showcase_artifacts`.
- `FEDVLR_PYTHON`: optional Python executable used to run FedVLR launcher. If not set, the service tries `FedVLR/.venv/Scripts/python.exe` on Windows and then falls back to the current Python executable.
- `FEDVLR_LAUNCH_TIMEOUT_SECONDS`: optional timeout for validate-only/dry-run subprocess calls.

Example `.env` content:

```text
FEDVLR_ROOT=../FedVLR
# FEDVLR_RESULTS_DIR=../FedVLR/outputs/results
# SHOWCASE_ARTIFACT_ROOT=../FedVLR/outputs/showcase_artifacts
# FEDVLR_PYTHON=../FedVLR/.venv/Scripts/python.exe
```

## Install and Run

```powershell
cd FedVLR-API
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API defaults to `http://127.0.0.1:8000`.

## Endpoints

- `GET /health`
- `GET /capabilities`
- `GET /experiment-schema`
- `POST /experiments/launch`
- `GET /experiments/launch/{launch_id}`
- `GET /experiments/summaries`
- `GET /experiments/{experiment_key}/summary`
- `GET /experiments/{experiment_key}/result`
- `GET /experiments/{experiment_key}/csv`
- `GET /showcase/comparison`
- `GET /showcase/scenarios`
- `GET /showcase/scenarios/{scenario_id}/manifest`
- `GET /showcase/scenarios/{scenario_id}/dataset`
- `GET /showcase/scenarios/{scenario_id}/metrics`
- `GET /showcase/scenarios/{scenario_id}/recommendations?limit=5|15|50&column=baseline|attack|defense|all`
- `GET /showcase/scenarios/{scenario_id}/security`
- `GET /showcase/scenarios/{scenario_id}/privacy`
- `GET /showcase/scenarios/{scenario_id}/report`
- `GET /showcase/images/{dataset}/{item_id}?size=thumb|full`
- `GET /showcase/scenarios/{scenario_id}/v3/profile`
- `GET /showcase/scenarios/{scenario_id}/v3/runtime`
- `GET /showcase/scenarios/{scenario_id}/v3/curves`
- `GET /showcase/scenarios/{scenario_id}/v3/target-manipulation`
- `GET /showcase/scenarios/{scenario_id}/v3/membership`
- `GET /showcase/scenarios/{scenario_id}/v3/update-leakage`
- `GET /showcase/scenarios/{scenario_id}/v3/aggregation-defense`
- `GET /showcase/scenarios/{scenario_id}/v3/privacy-defense`
- `GET /showcase/scenarios/{scenario_id}/v3/model-support`
- `GET /showcase/scenarios/{scenario_id}/v3/frontend-summary`
- `GET /showcase/scenarios/{scenario_id}/v3/report`
- `GET /workbench/options`
- `POST /workbench/validate`
- `POST /workbench/jobs`
- `GET /workbench/jobs/{job_id}`
- `GET /workbench/jobs/{job_id}/logs?tail=200`
- `GET /workbench/jobs/{job_id}/result`

## Experiment Launch

`POST /experiments/launch` accepts either:

- `{ "config": { ... }, "validate_only": true }`
- a bare unified experiment config object.

The config is passed to `FedVLR/scripts/launch_experiment.py` through a temporary JSON file.

Use `validate_only: true` or `dry_run: true` to validate mapping and capabilities without starting training. Use `strict_validation: true` only when unvalidated combinations should become hard errors.

## Result Scanning

Historical results are read from files ending with:

- `.experiment_summary.json`
- `.experiment_result.json`

`experiment_key` is derived from the relative result path and is used by the frontend as a stable read key. Do not change this rule without coordinating frontend changes.

CSV download is resolved by replacing the known JSON suffix with `.csv` under the same relative result path.

## Showcase Artifact Scanning

Showcase artifacts are read from `<SHOWCASE_ARTIFACT_ROOT>` when set, otherwise from `<FEDVLR_ROOT>/outputs/showcase_artifacts`. Each direct child directory is treated as a scenario.

The artifact APIs are read-only. They do not modify artifacts, start training, or delete outputs. Missing files in aggregate responses are returned as `null` with structured warnings. Single-file artifact endpoints return `404` when the requested file is absent. Invalid JSON is returned as `data: null` plus a warning instead of a server error.

Scenario list responses expose a public relative `path`, not the local absolute filesystem path.

The scanner recognizes Security Artifact V3 scenarios such as
`<SHOWCASE_ARTIFACT_ROOT>/amazon_beauty_poc_security_v3`. A V3 scenario may
contain:

- `scenario_profile.json`
- `runtime_timeline.json`
- `training_curves.json`
- `target_manipulation_metrics.json`
- `membership_inference_panel.json`
- `update_leakage_panel.json`
- `aggregation_defense_panel.json`
- `privacy_defense_panel.json`
- `model_support_panel.json`
- `frontend_summary.json`

`GET /showcase/scenarios` returns V3 light summary flags without reading large
recommendation lists: `has_v3`, `available_panels`, `supported_directions`,
`has_runtime`, `has_curves`, `has_target_manipulation`, `has_membership`,
`has_update_leakage`, `has_aggregation_defense`, `has_privacy_defense`,
`has_model_support`, and `has_images`.

The V3 endpoints serve structured panels for the frontend's four security
directions: recommendation manipulation, membership inference, update leakage,
and aggregation defense. `/v3/report` reads the ten small V3 JSON files and
returns missing panels as `null` with `missing_panel` warnings. Single-panel V3
endpoints return `404` when the requested panel file is absent. Invalid JSON is
returned as `data: null` with an `invalid_json` warning.

The API preserves V3 backend semantics. Do not rewrite
`attack_topk_hit=false`, `target_manipulation_index`,
`evidence_type=mixed_proxy`, `status=configured_only`,
`formal_dp_available=false`, or secure aggregation demo/simulation fields into
stronger claims. The service may add display-only fields such as
`display_status`, `display_warning`, and `display_tags`, but it must not invent
formal DP, checkpoint score, or attack-success evidence.

The showcase scanner also supports `model_security_capability_matrix` scenarios
exported under `outputs/showcase_artifacts/model_security_capability_matrix`.
The aggregate report can include:

- `model_security_capability_matrix`
- `supported_demos`
- `unsupported_reasons`
- `recommended_frontend_labels`

For large recommendation artifacts, `/showcase/scenarios/{scenario_id}/report`
returns a preview-limited `recommendation_comparison` with `preview_limit`,
`total_counts`, and `has_more`. Use
`/showcase/scenarios/{scenario_id}/recommendations?limit=5|15|50&column=baseline|attack|defense|all`
for paged recommendation rows. The recommendation endpoint returns only the
requested slice plus image metadata such as `thumbnail_url`, `local_image_url`,
`image_url`, `title`, `category`, `rank`, and `item_id`; it should not return the
full 25k+ row artifact to the frontend.

`GET /showcase/images/{dataset}/{item_id}?size=thumb|full` serves local Amazon
Beauty cached images only when the image is registered in
`FedVLR/datasets/AMAZON_BEAUTY_POC/item_image_manifest.json`. The endpoint
defaults to thumbnails, guards path segments, returns `404` for unregistered or
missing files, and does not expose local absolute paths. Recommendation and
target-rank artifacts may include `thumbnail_url` and `local_image_url` values
that point to this endpoint when a registered local image exists.

## Security Capability Boundary

The current backend exposes capabilities implemented by `FedVLR`: poisoning attacks, robust defenses, and risk observation. Differential privacy, homomorphic encryption, and secure aggregation are not formal implemented capabilities in the current training chain and should only be described as future extensions.

## Workbench Endpoints

`/workbench/*` powers the frontend attack-defense workbench validation and bounded smoke-job flow. It reads `FedVLR/configs/workbench_experiment_schema.json`, calls `FedVLR/scripts/generate_workbench_smoke_config.py` for normalized config generation, and starts only the whitelisted `FedVLR/scripts/run_workbench_smoke_job.py` runner.

- `GET /workbench/options` returns deduplicated datasets, the eight launchable model choices, adapter-required model notes, robust aggregation options, bounds, defaults, and Amazon target item options.
- `POST /workbench/validate` validates and normalizes a workbench payload without writing a job.
- `POST /workbench/jobs` writes a bounded job artifact under `FedVLR/outputs/workbench_jobs/{job_id}` and launches a restricted background smoke process with `subprocess.Popen`.
- `GET /workbench/jobs/{job_id}` returns `status`, `stage`, `progress`, timestamps, `error_message`, relative result/artifact pointers, and `source`.
- `GET /workbench/jobs/{job_id}/logs?tail=200` returns the tail of `run.log`; a missing log file for an existing job returns an empty list.
- `GET /workbench/jobs/{job_id}/result` reads `metrics_summary.json` and `result_pointer.json` when available. Job ids are restricted to safe characters and responses avoid local absolute paths.

Workbench jobs are still bounded smoke jobs, not a production queue. Some directions reuse existing V3 artifacts and must return `source=existing_artifact`; aggregation defense on KU with FedAvg/FedRAP can return `source=real_smoke` after a white-listed 1-epoch launcher run. Aggregation defense can still return `partial` when only config-only evidence exists. Do not present artifact reuse or smoke warnings as a full benchmark.

## Lightweight Validation

After Python code changes, run:

```powershell
python -m compileall -q app
```
